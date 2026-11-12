"""
llm_client.py – LLM Call Layer
================================
All LLM calls flow through this module.  It provides:

  robust_json_loads()     – tolerant JSON parser (fences, smart-quotes, trailing commas)
  _llm_call()             – Tier 1 single call with retry (litellm or openai backend)
  call_batch()            – 4-Tier Resilience Chain
  process_batches_async() – concurrent batch dispatcher

4-Tier Resilience Chain
-----------------------
Tier 1 │ Retry       Transient errors (rate-limit, timeout, connection)
        │             → exponential back-off, cfg.retries attempts
Tier 2 │ Split       JSON / parse error on a large batch
        │             → binary split, recurse on each half
Tier 3 │ Single      Any remaining failure on a small batch
        │             → one record at a time
Tier 4 │ UID Repair  Model omitted UIDs from its response
        │             → retry individually, stub if still absent

Backend toggle
--------------
Set the LLM_BACKEND environment variable (or edit DEFAULT_BACKEND below):

    LLM_BACKEND=litellm   # default — uses litellm.acompletion()
    LLM_BACKEND=openai    # uses openai.AsyncAzureOpenAI or openai.AsyncOpenAI

When using the openai backend:
  - Azure:  set AZURE_API_KEY, AZURE_API_BASE, AZURE_API_VERSION
            set cfg.model to the deployment name only (e.g. "dsaic-llm-general")
  - OpenAI: set OPENAI_API_KEY
            set cfg.model to the model name (e.g. "gpt-4o")
            set USE_AZURE=false in environment
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
import re
from typing import Any, Callable, Optional

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_exponential_jitter,
)
from tenacity.wait import wait_base

from .config import RunConfig

logger = logging.getLogger(__name__)

# ── Backend selection ──────────────────────────────────────────────────────
# Change DEFAULT_BACKEND here, or set the LLM_BACKEND environment variable.
# Valid values: "litellm"  |  "openai"
DEFAULT_BACKEND = "litellm"
LLM_BACKEND     = os.environ.get("LLM_BACKEND", DEFAULT_BACKEND).strip().lower()

if LLM_BACKEND not in ("litellm", "openai"):
    raise ValueError(
        f"LLM_BACKEND must be 'litellm' or 'openai', got '{LLM_BACKEND}'. "
        f"Set the LLM_BACKEND environment variable or edit DEFAULT_BACKEND in llm_client.py."
    )

logger.info("LLM backend: %s", LLM_BACKEND)

# ── Backend imports ────────────────────────────────────────────────────────
# litellm is always imported (it manages its own openai dependency internally).
# When LLM_BACKEND="openai", we additionally create a native openai client.
# IMPORTANT: litellm must be imported unconditionally because it configures
# its internal openai client state at import time.  Conditionally importing
# it can cause endpoint resolution failures in VNet/private-link setups.

import litellm

# Suppress litellm's noisy loggers — do NOT overwrite litellm.set_verbose
# as that can interfere with litellm's internal proxy/endpoint configuration.
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)

_LITELLM_RETRY_EXCEPTIONS = (
    litellm.exceptions.RateLimitError,
    litellm.exceptions.ServiceUnavailableError,
    litellm.exceptions.APIConnectionError,
    litellm.exceptions.Timeout,
    ConnectionError,
    TimeoutError,
)

# openai backend — only initialised when explicitly selected
_openai_client = None

if LLM_BACKEND == "openai":
    import openai

    _USE_AZURE = os.environ.get("USE_AZURE", "true").strip().lower() != "false"

    if _USE_AZURE:
        _openai_client = openai.AsyncAzureOpenAI(
            api_key        = os.environ.get("AZURE_API_KEY", ""),
            azure_endpoint = os.environ.get("AZURE_API_BASE", ""),
            api_version    = os.environ.get("AZURE_API_VERSION", "2024-02-01"),
        )
        logger.info("OpenAI backend: Azure (%s)", os.environ.get("AZURE_API_BASE", ""))
    else:
        _openai_client = openai.AsyncOpenAI(
            api_key = os.environ.get("OPENAI_API_KEY", ""),
        )
        logger.info("OpenAI backend: OpenAI direct")

    _OPENAI_RETRY_EXCEPTIONS = (
        openai.RateLimitError,
        openai.APIConnectionError,
        openai.APITimeoutError,
        openai.InternalServerError,
        ConnectionError,
        TimeoutError,
    )

# Unified retry exception tuple
_RETRY_EXCEPTIONS = (
    _LITELLM_RETRY_EXCEPTIONS if LLM_BACKEND == "litellm"
    else _OPENAI_RETRY_EXCEPTIONS if LLM_BACKEND == "openai"
    else _LITELLM_RETRY_EXCEPTIONS  # fallback
)


# ---------------------------------------------------------------------------
# robust_json_loads – tolerant JSON parser
# ---------------------------------------------------------------------------
def robust_json_loads(text: str) -> Any:
    """
    Parse JSON from LLM output, tolerating common formatting issues:
      - Markdown code fences (```json ... ```)
      - Smart / curly quotes
      - Trailing commas before } or ]
      - JSON array or object embedded in surrounding prose
      - Single quotes instead of double quotes
    Returns an empty list [] on complete failure.
    """
    if not text or not text.strip():
        return []

    original = text

    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)

    # Replace smart quotes
    text = (text
            .replace("\u201c", '"').replace("\u201d", '"')
            .replace("\u2018", "'").replace("\u2019", "'"))

    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract embedded array or object
    for pattern in [r"(\[[\s\S]*\])", r"(\{[\s\S]*\})"]:
        match = re.search(pattern, text)
        if match:
            candidate = re.sub(r",\s*([}\]])", r"\1", match.group(1))
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    # Single-quote structural fallback: only replace quotes that appear to act
    # as JSON string delimiters (preceded/followed by : , [ { or whitespace),
    # not apostrophes embedded inside word characters.
    # This avoids corrupting contractions like "customer's" → "customer"s".
    try:
        # Replace single-quoted JSON strings: 'value' → "value"
        # Pattern: single-quote preceded by : , [ { (with optional whitespace)
        # or at start, and followed by content up to a closing single-quote.
        sq_pattern = re.compile(
            r"(?<=[:\[{,\s])'((?:[^'\\]|\\.)*)'"
            r"|^'((?:[^'\\]|\\.)*)'",
            re.MULTILINE,
        )
        # Pick whichever alternative matched; the other group is None. Use an
        # explicit None check (not `or`) so an empty-string match ('') is kept
        # as "" instead of falling through to the None group and raising
        # TypeError on concatenation.
        converted = sq_pattern.sub(
            lambda m: '"' + (m.group(1) if m.group(1) is not None else m.group(2)) + '"',
            text,
        )
        return json.loads(converted)
    except (json.JSONDecodeError, re.error):
        pass

    # Last resort: salvage a truncated JSON response.
    #
    # Pre-check — escape-smart-quote retry:
    #   The main preprocessing replaced smart/curly quotes (“/”) with
    #   bare ASCII " which corrupts the JSON when those quotes appeared *inside*
    #   a string value (e.g. journal name "Vegueta" quoted in evidence text).
    #   Retry with them escaped as \" instead.
    try:
        alt = original
        alt = re.sub(r"```(?:json)?\s*", "", alt)
        alt = re.sub(r"```\s*$", "", alt)
        alt = (alt
               .replace("“", '\\"').replace("”", '\\"')
               .replace("‘", "'").replace("’", "'"))
        alt = re.sub(r",\s*([}\]])", r"\1", alt)
        result = json.loads(alt)
        if isinstance(result, dict):
            result = [result]
        if isinstance(result, list) and result:
            logger.warning(
                "robust_json_loads: escaped-smart-quote retry succeeded (len=%d).",
                len(original),
            )
            return result
    except Exception:
        pass

    # Pre-check 2 — unescaped inner quote fixer:
    #   LLMs sometimes quote a name or phrase with plain ASCII " inside a JSON
    #   string value, e.g.:
    #       "compliance_evidence": ["the journal "Nature" was discontinued"]
    #   The heuristic: scan character-by-character; when a " appears inside a
    #   string and the next non-whitespace character is NOT a structural JSON
    #   token (,:}]), the quote is an unescaped inner quote and is replaced with \".
    try:
        def _fix_inner_quotes(src: str) -> str:
            _STRUCT = frozenset(',:}]')
            out: list[str] = []
            i = 0
            n = len(src)
            while i < n:
                if src[i] != '"':
                    out.append(src[i]); i += 1; continue
                out.append('"'); i += 1          # opening quote of a string
                while i < n:
                    ch = src[i]
                    if ch == '\\':               # already-escaped char: copy both
                        out.append(ch); i += 1
                        if i < n: out.append(src[i]); i += 1
                        continue
                    if ch == '"':
                        j = i + 1               # peek past whitespace
                        while j < n and src[j] in ' \t\r\n': j += 1
                        if j >= n or src[j] in _STRUCT:
                            out.append('"'); i += 1; break   # real string end
                        out.append('\\"'); i += 1; continue  # inner quote
                    out.append(ch); i += 1
            return ''.join(out)

        fixed  = _fix_inner_quotes(text)
        result = json.loads(fixed)
        if isinstance(result, dict):
            result = [result]
        if isinstance(result, list) and result:
            logger.warning(
                "robust_json_loads: inner-quote fix succeeded (len=%d).",
                len(original),
            )
            return result
    except Exception:
        pass

    # Strategy A – iterative raw_decode:
    #   Walk the outer array and use json.JSONDecoder.raw_decode() to parse
    #   each object individually.  Stops at the first incomplete object and
    #   returns all fully-parsed ones.  Correctly handles any content inside
    #   string values (escaped quotes, brackets, etc.).
    try:
        decoder  = json.JSONDecoder()
        salvaged: list[dict] = []
        arr_start = text.find("[")
        if arr_start >= 0:
            pos = arr_start + 1
            while pos < len(text):
                while pos < len(text) and text[pos] in " \t\r\n,":
                    pos += 1
                if pos >= len(text) or text[pos] == "]":
                    break
                if text[pos] != "{":
                    break
                try:
                    obj, end_pos = decoder.raw_decode(text, pos)
                    if isinstance(obj, dict) and "uid" in obj:
                        salvaged.append(obj)
                    pos = end_pos
                except json.JSONDecodeError:
                    break   # hit the incomplete/truncated object — stop here
        if salvaged:
            logger.warning(
                "robust_json_loads: iterative salvage — %d complete record(s) recovered "
                "from truncated response (len=%d); incomplete tail will be retried.",
                len(salvaged), len(original),
            )
            return salvaged
    except Exception as _e_a:
        logger.debug("robust_json_loads: Strategy A failed unexpectedly: %s", _e_a)

    # Strategy B – escape-aware structural close:
    #   Walk the text character-by-character tracking in-string state (so
    #   escaped quotes \" and brackets inside strings are ignored).  Finds the
    #   last comma that lies outside any string, truncates there, then closes
    #   every open bracket/brace in reverse order.  Handles the single-record
    #   case where all important fields are present but the last list field is
    #   cut off mid-string.
    try:
        def _scan(src: str) -> tuple[bool, list[str], int]:
            """Return (ended_in_string, open_stack, last_structural_comma)."""
            in_s   = False
            stk: list[str] = []
            last_c = -1
            k      = 0
            while k < len(src):
                ch = src[k]
                if in_s:
                    if ch == "\\":
                        k += 2          # skip escaped char (\" or \\)
                        continue
                    elif ch == '"':
                        in_s = False
                else:
                    if ch == '"':
                        in_s = True
                    elif ch in "[{":
                        stk.append(ch)
                    elif ch in "]}":
                        if stk:
                            stk.pop()
                    elif ch == ",":
                        last_c = k
                k += 1
            return in_s, stk, last_c

        _in_str, _stack, last_comma = _scan(text)
        if last_comma > 0:
            head                  = text[:last_comma]
            _in_str2, stack2, _lc = _scan(head)
            close_map = {"{": "}", "[": "]"}
            closing   = "".join(close_map[c] for c in reversed(stack2))
            candidate = head + closing
            try:
                result = json.loads(candidate)
            except json.JSONDecodeError as _jde:
                logger.debug(
                    "robust_json_loads: Strategy B candidate (last_comma=%d, "
                    "stack2=%r) failed json.loads: %s. candidate[:300]=%r",
                    last_comma, stack2, _jde, candidate[:300],
                )
                raise
            if isinstance(result, dict):
                result = [result]
            if isinstance(result, list):
                valid = [r for r in result if isinstance(r, dict) and "uid" in r]
                if valid:
                    logger.warning(
                        "robust_json_loads: structural salvage — %d partial record(s) "
                        "recovered from truncated response (len=%d). "
                        "Increase MAX_TOKENS if this recurs.",
                        len(valid), len(original),
                    )
                    return valid
    except Exception as _e_b:
        logger.debug("robust_json_loads: Strategy B failed: %s", _e_b)

    logger.warning(
        "robust_json_loads: failed to parse (len=%d). First 300 chars: %s",
        len(original), repr(original[:300])
    )
    raise ValueError(
        f"robust_json_loads: all recovery attempts failed (len={len(original)})"
    )


# ---------------------------------------------------------------------------
# _make_retry – build a tenacity @retry decorator from cfg.retries
# ---------------------------------------------------------------------------

# B4 fix: per-coroutine response storage via contextvars (replaces the
# module-level dict that caused a race condition under concurrency > 1).
_current_response: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "_current_response", default=None
)

# Per-coroutine record count so _record_usage attributes cost to the right
# number of records regardless of concurrent batches.
_batch_n_records: contextvars.ContextVar[int] = contextvars.ContextVar(
    "_batch_n_records", default=1
)

# B2 fix: module-level cost tracker — set by pipeline.py before classification,
# _llm_call records usage after every successful call.
_cost_tracker: Any = None            # Optional[CostTracker]
# Module label for cost attribution. A ContextVar, not a global: `rca run`
# classifies several modules concurrently, and each asyncio task must keep
# its own label (tasks copy the context when they are created).
_cost_tracker_module: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_cost_tracker_module", default=""
)

# B1/B3 fix: prompt suffix — appended to every system_prompt by call_batch().
# Set before each module's classification with confidence instructions and/or
# feedback few-shot examples.  Per task (ContextVar) so concurrent modules in
# `rca run` each get their own suffix.
_system_prompt_suffix: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_system_prompt_suffix", default=""
)

# Smart feedback strategy: per-batch suffix overrides set by pipeline.py.
# When set, process_batches_async prepends _per_batch_suffixes[slot] to the
# base system_prompt before calling call_batch, so each batch gets its own
# tailored few-shot examples.  _system_prompt_suffix is set to "" in this mode.
_per_batch_suffixes: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "_per_batch_suffixes", default=None
)

# Logprobs safety: some Azure deployments don't support logprobs and return
# a 400 error.  We track this per-model-string so that one model's failure
# does not disable logprobs for a different model in the same process.
# Key: cfg.model string  →  Value: False if logprobs are known unsupported.
_logprobs_unsupported_models: set[str] = set()


def _logprobs_supported(model: str) -> bool:
    """Return True if logprobs have not previously failed for this model."""
    return model not in _logprobs_unsupported_models


def _disable_logprobs(model: str) -> None:
    """Mark a model as not supporting logprobs (persists for the process lifetime)."""
    _logprobs_unsupported_models.add(model)


# ---------------------------------------------------------------------------
# Process-wide rate limit gate
# ---------------------------------------------------------------------------
# When any concurrent batch receives a 429, it acquires _rl_lock, sets
# _rl_event, waits out the Retry-After window, then clears _rl_event.
# Every other batch checks _rl_event before each API call and waits until
# it is cleared.  This prevents the thundering-herd pattern where all
# concurrent batches hit the limit, all back off by the same amount, and
# all retry simultaneously — hitting the limit again.
#
# _rl_lock ensures only one coroutine drives the wait; all others just block
# on the event until the window passes.

_rl_event: asyncio.Event | None = None   # None until first asyncio loop starts
_rl_lock:  asyncio.Lock | None  = None


def _get_rl_primitives() -> tuple[asyncio.Event, asyncio.Lock]:
    """Return (or lazily create) the rate-limit gate primitives for the running loop."""
    global _rl_event, _rl_lock
    # Re-create if the event loop has changed (e.g. between asyncio.run() calls in tests)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if _rl_event is None or _rl_lock is None:
        _rl_event = asyncio.Event()
        _rl_lock  = asyncio.Lock()
    return _rl_event, _rl_lock


async def _wait_if_rate_limited() -> None:
    """Block until the process-wide rate limit gate is clear."""
    event, _ = _get_rl_primitives()
    if event.is_set():
        logger.debug("Rate limit gate: waiting for backoff window to clear")
        await asyncio.wait_for(
            asyncio.shield(asyncio.ensure_future(_event_cleared(event))),
            timeout=180,
        )


async def _event_cleared(event: asyncio.Event) -> None:
    """Coroutine that returns once the event is no longer set."""
    while event.is_set():
        await asyncio.sleep(0.25)


async def _trigger_rl_gate(wait_s: float) -> None:
    """
    Set the rate limit gate, sleep for wait_s, then clear it.
    Only one coroutine drives the wait at a time (protected by _rl_lock).
    """
    event, lock = _get_rl_primitives()
    if lock.locked():
        # Another coroutine is already handling the backoff — just wait for it
        await _wait_if_rate_limited()
        return
    async with lock:
        event.set()
        logger.info("Rate limit gate: pausing all batches for %.0f s", wait_s)
        await asyncio.sleep(wait_s)
        event.clear()
        logger.info("Rate limit gate: resuming")


class _wait_rate_limit(wait_base):
    """
    Tenacity wait strategy that honours the Retry-After header from Azure 429
    responses, falling back to exponential backoff with jitter.

    Azure TPM rate limits reset on a 60-second window.  The Retry-After header
    tells us exactly how long to wait; when it is absent we use exponential
    backoff (2→4→8…) capped at 90 s with ±2 s jitter to break the thundering
    herd that occurs when all concurrent batches hit the limit simultaneously
    and then all retry at the same instant.
    """
    def __call__(self, retry_state) -> float:
        exc = retry_state.outcome.exception()
        if exc is not None:
            # Try to read Retry-After from the raw HTTP response attached to the
            # exception (present on litellm.RateLimitError and openai.RateLimitError).
            response = getattr(exc, "response", None)
            if response is not None:
                headers = getattr(response, "headers", {}) or {}
                retry_after = headers.get("Retry-After") or headers.get("retry-after")
                if retry_after:
                    try:
                        wait = float(retry_after) + 1.0  # +1 s safety margin
                        logger.info(
                            "Rate limit: honouring Retry-After=%.0f s (attempt %d)",
                            wait, retry_state.attempt_number,
                        )
                        return wait
                    except (ValueError, TypeError):
                        pass
        # Fallback: exponential backoff with jitter
        exp = wait_exponential_jitter(initial=2, max=90, jitter=2)
        return exp(retry_state)


def _make_retry(retries: int):
    """
    Return a tenacity retry decorator configured with the given attempt count.

    Uses _wait_rate_limit which reads Retry-After headers from 429 responses and
    falls back to exponential backoff with jitter to avoid thundering-herd retries.
    """
    return retry(
        stop=stop_after_attempt(retries),
        wait=_wait_rate_limit(),
        retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
        reraise=True,
    )


# ---------------------------------------------------------------------------
# Single LLM call — litellm backend
# ---------------------------------------------------------------------------
async def _llm_call_litellm(messages: list[dict], cfg: RunConfig) -> str:
    @_make_retry(cfg.retries)
    async def _call():
        import time
        kwargs = dict(
            model       = cfg.model,
            messages    = messages,
            temperature = cfg.temperature,
            max_tokens  = cfg.max_tokens,
            timeout     = cfg.timeout,
        )
        # Request logprobs when confidence scoring is enabled AND supported for this model
        if getattr(cfg, "enable_confidence", False) and _logprobs_supported(cfg.model):
            kwargs["logprobs"] = True
            kwargs["top_logprobs"] = 1

        # Wait if another batch triggered the process-wide rate limit gate
        await _wait_if_rate_limited()

        t0 = time.monotonic()
        try:
            response = await litellm.acompletion(**kwargs)
        except Exception as e:
            # If the error is due to logprobs not being supported, retry without
            if _logprobs_supported(cfg.model) and "logprobs" in kwargs and "logprobs" in str(e).lower():
                _disable_logprobs(cfg.model)
                logger.warning("Logprobs not supported by '%s' — disabling: %s", cfg.model, e)
                kwargs.pop("logprobs", None)
                kwargs.pop("top_logprobs", None)
                t0 = time.monotonic()
                response = await litellm.acompletion(**kwargs)
            else:
                # On rate limit: trigger the process-wide gate so all concurrent
                # batches pause for the same backoff window, then re-raise so
                # tenacity handles the per-call retry.
                if isinstance(e, _RETRY_EXCEPTIONS):
                    response_obj = getattr(e, "response", None)
                    headers = getattr(response_obj, "headers", {}) or {}
                    retry_after = headers.get("Retry-After") or headers.get("retry-after")
                    wait_s = float(retry_after) + 1.0 if retry_after else 30.0
                    asyncio.ensure_future(_trigger_rl_gate(wait_s))
                raise
        duration_s = time.monotonic() - t0

        # B4 fix: store in coroutine-local contextvar (not a shared dict)
        _current_response.set(response)

        # B2 fix: record usage on the registered cost tracker
        _record_usage(response, duration_s=duration_s)

        return response.choices[0].message.content or ""

    return await _call()


# ---------------------------------------------------------------------------
# Single LLM call — openai backend
# ---------------------------------------------------------------------------
async def _llm_call_openai(messages: list[dict], cfg: RunConfig) -> str:
    @_make_retry(cfg.retries)
    async def _call():
        import time
        kwargs = dict(
            model       = cfg.model,
            messages    = messages,
            temperature = cfg.temperature,
            max_tokens  = cfg.max_tokens,
            timeout     = cfg.timeout,
        )
        # Request logprobs when confidence scoring is enabled AND supported for this model
        if getattr(cfg, "enable_confidence", False) and _logprobs_supported(cfg.model):
            kwargs["logprobs"] = True
            kwargs["top_logprobs"] = 1

        # For Azure the model is the deployment name.
        # For direct OpenAI it is the model name (e.g. gpt-4o).
        # Wait if another batch triggered the process-wide rate limit gate
        await _wait_if_rate_limited()

        t0 = time.monotonic()
        try:
            response = await _openai_client.chat.completions.create(**kwargs)
        except Exception as e:
            if _logprobs_supported(cfg.model) and "logprobs" in kwargs and "logprobs" in str(e).lower():
                _disable_logprobs(cfg.model)
                logger.warning("Logprobs not supported by '%s' — disabling: %s", cfg.model, e)
                kwargs.pop("logprobs", None)
                kwargs.pop("top_logprobs", None)
                t0 = time.monotonic()
                response = await _openai_client.chat.completions.create(**kwargs)
            else:
                if isinstance(e, _RETRY_EXCEPTIONS):
                    response_obj = getattr(e, "response", None)
                    headers = getattr(response_obj, "headers", {}) or {}
                    retry_after = headers.get("Retry-After") or headers.get("retry-after")
                    wait_s = float(retry_after) + 1.0 if retry_after else 30.0
                    asyncio.ensure_future(_trigger_rl_gate(wait_s))
                raise
        duration_s = time.monotonic() - t0

        # B4 fix: store in coroutine-local contextvar
        _current_response.set(response)

        # B2 fix: record usage on the registered cost tracker
        _record_usage(response, duration_s=duration_s)

        return response.choices[0].message.content or ""

    return await _call()


# ---------------------------------------------------------------------------
# Unified single LLM call (Tier 1 retry applied dynamically from cfg)
# ---------------------------------------------------------------------------
async def _llm_call(messages: list[dict], cfg: RunConfig) -> str:
    """
    Tier 1: single async LLM completion with exponential-backoff retry.
    Delegates to litellm or openai backend based on LLM_BACKEND setting.
    """
    if LLM_BACKEND == "openai":
        return await _llm_call_openai(messages, cfg)
    return await _llm_call_litellm(messages, cfg)


def get_last_response() -> Any:
    """Return the raw response from the most recent LLM call in the current coroutine.

    B4 fix: uses contextvars so each concurrent coroutine gets its own value.
    """
    return _current_response.get(None)


# ---------------------------------------------------------------------------
# B2 fix: cost tracker recording helper
# ---------------------------------------------------------------------------
def _record_usage(response: Any, duration_s: float = 0.0) -> None:
    """Record token usage on the registered cost tracker (if any)."""
    if _cost_tracker is None:
        return
    try:
        _cost_tracker.record_from_response(
            module=_cost_tracker_module.get() or "unknown",
            response=response,
            n_records=_batch_n_records.get(1),
            duration_s=duration_s,
        )
    except Exception as e:
        logger.debug("_record_usage: %s", e)


def register_cost_tracker(tracker: Any, module: str = "") -> None:
    """Register a cost tracker to receive usage data from every LLM call."""
    global _cost_tracker
    _cost_tracker = tracker
    _cost_tracker_module.set(module)


def set_cost_tracker_module(module: str) -> None:
    """Update the module label for cost attribution (for the current task)."""
    _cost_tracker_module.set(module)


def get_cost_tracker_module() -> str:
    """The module label costs are currently attributed to (for the current task)."""
    return _cost_tracker_module.get()


def unregister_cost_tracker() -> None:
    """Remove the cost tracker."""
    global _cost_tracker
    _cost_tracker = None
    _cost_tracker_module.set("")


def get_cost_tracker() -> Any:
    """Return the currently registered cost tracker, or None."""
    return _cost_tracker


# ---------------------------------------------------------------------------
# B1/B3 fix: prompt suffix registration
# ---------------------------------------------------------------------------
def set_system_prompt_suffix(suffix: str) -> None:
    """Set a suffix that call_batch() appends to every system prompt.

    Used by pipeline.py to inject confidence instructions and feedback
    few-shot examples without modifying the auto-generated module files.
    """
    _system_prompt_suffix.set(suffix)


def get_system_prompt_suffix() -> str:
    """The suffix call_batch() will append (for the current task)."""
    return _system_prompt_suffix.get()


def clear_system_prompt_suffix() -> None:
    """Remove the prompt suffix."""
    _system_prompt_suffix.set("")


def set_per_batch_suffixes(suffixes: list[str] | None) -> None:
    """Set per-batch system prompt suffixes for strategy='smart'.

    When set, process_batches_async appends suffixes[slot] to the base
    system_prompt for each batch slot instead of using _system_prompt_suffix
    for feedback.  pipeline.py sets _system_prompt_suffix to "" in this mode
    so call_batch does not double-append anything.
    """
    _per_batch_suffixes.set(list(suffixes) if suffixes is not None else None)


def clear_per_batch_suffixes() -> None:
    """Clear per-batch suffix overrides."""
    _per_batch_suffixes.set(None)


# ---------------------------------------------------------------------------
# call_batch – 4-Tier Resilience Chain
# ---------------------------------------------------------------------------
async def call_batch(
    records: list[dict[str, str]],
    system_prompt: str,
    user_prompt_template: str,
    cfg: RunConfig,
    parse_fn: Optional[Callable] = None,
    _allow_uid_repair: bool = True,
    _allow_degradation: bool = True,
    _split_depth: int = 0,
) -> list[dict[str, Any]]:
    """
    Process a batch of records through the LLM with full resilience.

    Parameters
    ----------
    records               list of dicts, each containing at least {uid, text}
    system_prompt         classification instructions for the system turn
    user_prompt_template  template string with a {records_json} placeholder
    cfg                   RunConfig
    parse_fn              optional per-record transform applied after parsing
    _allow_uid_repair     internal flag — False prevents recursive Tier 4 loops
    _allow_degradation    internal flag — False prevents recursive Tier 2/3 loops
    _split_depth          internal counter — tracks binary-split recursion depth

    Returns
    -------
    list of enrichment dicts, one per input record
    """
    if not records:
        return []

    records_json = json.dumps(records, indent=2, ensure_ascii=False)
    user_prompt  = user_prompt_template.replace("{records_json}", records_json)

    # Set per-coroutine record count so _record_usage attributes cost correctly.
    _batch_n_records.set(len(records))

    # B1/B3 fix: append confidence instruction and/or feedback few-shot
    # examples if a suffix has been registered by pipeline.py.
    effective_prompt = system_prompt
    suffix = _system_prompt_suffix.get()
    if suffix:
        effective_prompt = system_prompt + suffix

    messages     = [
        {"role": "system", "content": effective_prompt},
        {"role": "user",   "content": user_prompt},
    ]

    # Exceptions that trigger Tier 2/3 degradation
    _degradation_errors = (json.JSONDecodeError, ValueError, RetryError)

    try:
        raw    = await _llm_call(messages, cfg)
        parsed = robust_json_loads(raw)

        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            raise ValueError(f"Expected list, got {type(parsed)}")

        # Tier 4: UID repair (disabled for recursive calls to prevent loops)
        if _allow_uid_repair:
            parsed = await _uid_repair(parsed, records, system_prompt, user_prompt_template, cfg)

        if parse_fn:
            parsed = [parse_fn(r) for r in parsed]

        return parsed

    except _degradation_errors as e:
        if not _allow_degradation:
            # Already inside a Tier 2/3 call — don't recurse, just stub errors
            logger.error("Tier 2/3 degradation exhausted for batch of %d: %s", len(records), e)
            return [{"uid": r.get("uid", ""), "_error": str(e)} for r in records]

        logger.warning("Tier 2: degradation trigger for batch of %d: %s", len(records), e)

        if len(records) > 2:
            return await _tier2_split(records, system_prompt, user_prompt_template, cfg, parse_fn,
                                      _depth=_split_depth)
        return await _tier3_single(records, system_prompt, user_prompt_template, cfg, parse_fn)

    except Exception as e:
        logger.error("LLM call failed for batch of %d: %s", len(records), e)
        return [{"uid": r.get("uid", ""), "_error": str(e)} for r in records]


# ---------------------------------------------------------------------------
# Tier 2 – binary split
# ---------------------------------------------------------------------------
async def _tier2_split(
    records: list[dict],
    system_prompt: str,
    user_prompt_template: str,
    cfg: RunConfig,
    parse_fn: Optional[Callable] = None,
    _depth: int = 0,
) -> list[dict[str, Any]]:
    _MAX_SPLIT_DEPTH = 4  # prevents runaway recursion on persistently bad batches
    mid = len(records) // 2
    logger.info(
        "Tier 2 split (depth=%d): %d → %d + %d",
        _depth, len(records), mid, len(records) - mid,
    )
    if _depth >= _MAX_SPLIT_DEPTH:
        logger.warning(
            "Tier 2 split depth limit (%d) reached with %d records — "
            "falling through to Tier 3 single-record processing.",
            _MAX_SPLIT_DEPTH, len(records),
        )
        return await _tier3_single(records, system_prompt, user_prompt_template, cfg, parse_fn)

    left  = await call_batch(records[:mid], system_prompt, user_prompt_template, cfg, parse_fn,
                              _split_depth=_depth + 1)
    right = await call_batch(records[mid:], system_prompt, user_prompt_template, cfg, parse_fn,
                              _split_depth=_depth + 1)
    return left + right


# ---------------------------------------------------------------------------
# Tier 3 – one record at a time
# ---------------------------------------------------------------------------
async def _tier3_single(
    records: list[dict],
    system_prompt: str,
    user_prompt_template: str,
    cfg: RunConfig,
    parse_fn: Optional[Callable] = None,
) -> list[dict[str, Any]]:
    logger.info("Tier 3 single: processing %d records individually", len(records))
    results = []
    for record in records:
        try:
            result = await call_batch(
                [record], system_prompt, user_prompt_template, cfg, parse_fn,
                _allow_degradation=False,
            )
            results.extend(result)
        except Exception as e:
            logger.error("Tier 3 failed uid=%s: %s", record.get("uid"), e)
            results.append({"uid": record.get("uid", ""), "_error": str(e)})
    return results


# ---------------------------------------------------------------------------
# Tier 4 – UID repair
# ---------------------------------------------------------------------------
async def _uid_repair(
    parsed: list[dict],
    records: list[dict],
    system_prompt: str,
    user_prompt_template: str,
    cfg: RunConfig,
) -> list[dict]:
    expected = {str(r.get("uid", "")) for r in records}
    returned = {str(r.get("uid", "")) for r in parsed}
    missing  = expected - returned

    if not missing:
        return parsed

    logger.info("Tier 4 UID repair: %d missing UIDs", len(missing))
    uid_to_record = {str(r.get("uid", "")): r for r in records}

    for uid in missing:
        original = uid_to_record.get(uid)
        if original:
            try:
                result = await call_batch(
                    [original], system_prompt, user_prompt_template, cfg,
                    _allow_uid_repair=False,   # prevent recursive Tier 4 loops
                )
                # Log warnings for any error records in the result
                for r in result:
                    if "_error" in r:
                        logger.warning(
                            "Tier 4 repair failed for uid=%s: %s",
                            r.get("uid", uid), r.get("_error", "?")
                        )
                parsed.extend(result)
            except Exception as e:
                logger.error("Tier 4 repair exception uid=%s: %s", uid, e)
                parsed.append({"uid": uid, "_error": "uid_repair_failed"})
        else:
            parsed.append({"uid": uid, "_error": "uid_not_found"})

    return parsed


# ---------------------------------------------------------------------------
# Concurrent batch dispatcher
# ---------------------------------------------------------------------------
async def process_batches_async(
    batches: list[list[dict]],
    system_prompt: str,
    user_prompt_template: str,
    cfg: RunConfig,
    parse_fn: Optional[Callable] = None,
) -> list[dict[str, Any]]:
    """
    Dispatch all batches concurrently, capped at cfg.concurrency.
    Returns a flat list of all enrichment dicts.

    Batches are staggered by a small random delay (0–1 s × slot index) before
    they first acquire the semaphore.  This spreads the initial wave of API
    calls across time and significantly reduces the chance of all concurrent
    workers hitting the rate limit simultaneously and then all retrying at
    the same instant (thundering herd).
    """
    import random
    semaphore   = asyncio.Semaphore(cfg.concurrency)
    all_results: list[dict[str, Any]] = []

    async def _process_one(batch: list[dict], slot: int) -> list[dict]:
        # Stagger launch: each slot waits a small random offset so batches
        # do not all fire in the same millisecond.
        if slot > 0:
            await asyncio.sleep(random.uniform(0, min(slot * 0.5, 5.0)))
        # Smart feedback strategy: each batch slot gets its own pre-built
        # suffix (confidence instruction + batch-specific few-shot examples).
        # Slots out of range fall back silently to the base prompt.
        effective_sp = system_prompt
        per_batch = _per_batch_suffixes.get()
        if per_batch is not None:
            if slot < len(per_batch):
                batch_suffix = per_batch[slot]
                if batch_suffix:
                    effective_sp = system_prompt + batch_suffix
            else:
                logger.debug(
                    "_process_one slot %d out of range for _per_batch_suffixes "
                    "(len=%d) — using base prompt",
                    slot, len(per_batch),
                )
        async with semaphore:
            return await call_batch(
                batch, effective_sp, user_prompt_template, cfg, parse_fn
            )

    batch_results = await asyncio.gather(
        *[_process_one(b, i) for i, b in enumerate(batches)],
        return_exceptions=True,
    )

    for i, result in enumerate(batch_results):
        if isinstance(result, Exception):
            logger.error("Batch %d raised: %s", i, result)
            for rec in batches[i]:
                all_results.append({"uid": rec.get("uid", ""), "_error": str(result)})
        else:
            all_results.extend(result)

    return all_results
