"""
language.py – Language Detection & Multi-Language Support
==========================================================
Pre-processes non-English transcripts for more accurate classification.

Two strategies:
  1. Translation-first: Translate non-English transcripts to English before
     classification (LLMs classify more accurately in English).
  2. Prompt adaptation: Keep the original language but adjust prompts to
     instruct the LLM about the expected language.

Language detection uses a lightweight heuristic approach that doesn't
require external libraries (falls back to character-range analysis and
common word detection).  If `langdetect` is installed, uses it instead.

Usage:
  from language import (
      detect_language, preprocess_multilingual,
      LanguageConfig, translate_batch,
  )

  # Detect languages in a DataFrame
  df = detect_language(df, text_col="transcript")

  # Preprocess: translate non-English, add language metadata
  df = await preprocess_multilingual(df, cfg, strategy="translate")
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from ..config import RunConfig

logger = logging.getLogger(__name__)

# Try to import langdetect; fall back to heuristics
_HAS_LANGDETECT = False
try:
    from langdetect import detect as _langdetect_detect
    from langdetect import DetectorFactory
    DetectorFactory.seed = 42  # Reproducible results
    _HAS_LANGDETECT = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
_COMMON_ENGLISH_WORDS = frozenset({
    "the", "and", "is", "in", "to", "of", "a", "for", "that", "this",
    "with", "it", "was", "on", "are", "be", "have", "from", "or", "an",
    "has", "not", "but", "can", "had", "all", "their", "will", "there",
    "been", "would", "about", "which", "when", "your", "what", "some",
    "them", "than", "its", "into", "other", "could", "time", "very",
    "just", "know", "how", "after", "also", "did", "get", "any",
    "please", "thank", "thanks", "help", "issue", "problem", "account",
})

_COMMON_SPANISH_WORDS = frozenset({
    "el", "la", "de", "en", "los", "del", "las", "por", "con", "una",
    "para", "es", "que", "no", "se", "su", "un", "al", "como", "más",
})

_COMMON_FRENCH_WORDS = frozenset({
    "le", "la", "de", "les", "des", "un", "une", "du", "en", "est",
    "pour", "dans", "que", "pas", "sur", "avec", "ce", "sont", "au",
})

_COMMON_GERMAN_WORDS = frozenset({
    "der", "die", "und", "den", "das", "ist", "von", "ein", "eine",
    "mit", "auf", "für", "sich", "dem", "nicht", "des", "als", "auch",
})

_COMMON_PORTUGUESE_WORDS = frozenset({
    "de", "que", "do", "da", "em", "para", "com", "não", "uma", "os",
    "no", "se", "na", "por", "mais", "as", "dos", "como", "mas", "foi",
})

_LANG_WORD_SETS: dict[str, frozenset[str]] = {
    "en": _COMMON_ENGLISH_WORDS,
    "es": _COMMON_SPANISH_WORDS,
    "fr": _COMMON_FRENCH_WORDS,
    "de": _COMMON_GERMAN_WORDS,
    "pt": _COMMON_PORTUGUESE_WORDS,
}

_LANG_NAMES: dict[str, str] = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "pt": "Portuguese", "it": "Italian", "nl": "Dutch", "pl": "Polish",
    "ru": "Russian", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
    "ar": "Arabic", "hi": "Hindi", "tr": "Turkish", "sv": "Swedish",
    "da": "Danish", "no": "Norwegian", "fi": "Finnish",
}


def detect_language_text(
    text: str,
    en_min_score: float = 0.15,
    en_margin: float = 0.05,
) -> tuple[str, float]:
    """
    Detect the language of a single text string.

    Parameters
    ----------
    text        : text to detect
    en_min_score : minimum English word-frequency score to consider English
                   (configurable to avoid over-classifying Romance-language text)
    en_margin   : how much the best non-English score must exceed the English
                  score before we prefer the non-English language

    Returns
    -------
    (lang_code, confidence) — e.g. ("en", 0.95)
    """
    if not text or len(text.strip()) < 10:
        return "en", 0.5  # default for very short text

    # Strategy 1: use langdetect if available
    if _HAS_LANGDETECT:
        try:
            lang = _langdetect_detect(text)
            return lang, 0.85  # langdetect doesn't provide confidence easily
        except Exception:
            pass

    # Strategy 2: heuristic word-frequency approach
    words = re.findall(r"\b[a-zA-ZÀ-ÿ]+\b", text.lower())
    if not words:
        return "en", 0.3

    total = len(words)
    lang_scores: dict[str, float] = {}
    for lang, word_set in _LANG_WORD_SETS.items():
        matches = sum(1 for w in words if w in word_set)
        lang_scores[lang] = matches / total

    best_lang = max(lang_scores, key=lambda k: lang_scores[k])
    best_score = lang_scores[best_lang]

    # If English score is strong enough and close to the best, prefer English.
    # Both thresholds are now parameters so callers can tune them.
    en_score = lang_scores.get("en", 0)
    if en_score > en_min_score and (best_score - en_score) < en_margin:
        return "en", en_score

    confidence = min(best_score * 2, 1.0)  # Scale up
    return best_lang, round(confidence, 3)


def detect_language(
    df: pd.DataFrame,
    text_col: str = "transcript",
    lang_col: str = "_detected_language",
    conf_col: str = "_language_confidence",
    en_min_score: float = 0.15,
    en_margin: float = 0.05,
) -> pd.DataFrame:
    """
    Add language detection columns to a DataFrame.

    Adds:
      _detected_language: ISO 639-1 code (e.g. "en", "es")
      _language_confidence: detection confidence 0-1

    Parameters
    ----------
    en_min_score : forwarded to detect_language_text — minimum English score
    en_margin    : forwarded to detect_language_text — margin over best non-English
    """
    df = df.copy()
    langs = []
    confs = []

    for _, row in df.iterrows():
        text = str(row.get(text_col, ""))
        lang, conf = detect_language_text(text, en_min_score=en_min_score, en_margin=en_margin)
        langs.append(lang)
        confs.append(conf)

    df[lang_col] = langs
    df[conf_col] = confs

    # Log distribution
    lang_counts = Counter(langs)
    total = len(df)
    non_en = total - lang_counts.get("en", 0)
    logger.info(
        "Language detection: %d records — %d English, %d non-English",
        total, lang_counts.get("en", 0), non_en,
    )
    for lang, count in lang_counts.most_common():
        name = _LANG_NAMES.get(lang, lang)
        logger.info("  %s (%s): %d (%.1f%%)", name, lang, count, count / total * 100)

    return df


# ---------------------------------------------------------------------------
# Translation via LLM
# ---------------------------------------------------------------------------
async def translate_text(
    text: str,
    source_lang: str,
    target_lang: str = "en",
    cfg: Optional[RunConfig] = None,
) -> str:
    """Translate a single text using the LLM."""
    from llm_client import _llm_call

    if cfg is None:
        cfg = RunConfig()

    source_name = _LANG_NAMES.get(source_lang, source_lang)
    target_name = _LANG_NAMES.get(target_lang, target_lang)

    messages = [
        {
            "role": "system",
            "content": (
                f"You are a professional translator. Translate the following "
                f"{source_name} text to {target_name}. "
                f"Preserve technical terms, product names, and error messages in their original form. "
                f"Return ONLY the translation, no explanations."
            ),
        },
        {"role": "user", "content": text},
    ]

    try:
        translated = await _llm_call(messages, cfg)
        return translated.strip()
    except Exception as e:
        logger.warning("Translation failed for %s→%s: %s", source_lang, target_lang, e)
        return text  # return original on failure


async def translate_batch(
    records: list[dict[str, str]],
    source_lang: str,
    cfg: RunConfig,
    target_lang: str = "en",
) -> list[dict[str, str]]:
    """
    Translate a batch of records from source_lang to target_lang.
    Returns records with translated text (original preserved as _original_text).
    """
    semaphore = asyncio.Semaphore(cfg.concurrency)

    async def _translate_one(record: dict) -> dict:
        async with semaphore:
            original = record["text"]
            translated = await translate_text(original, source_lang, target_lang, cfg)
            return {
                **record,
                "text": translated,
                "_original_text": original,
                "_translated_from": source_lang,
            }

    results = await asyncio.gather(
        *[_translate_one(r) for r in records],
        return_exceptions=True,
    )

    translated_records = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("Translation error: %s", r)
        else:
            translated_records.append(r)

    logger.info("Translated %d/%d records from %s to %s",
                 len(translated_records), len(records), source_lang, target_lang)
    return translated_records


# ---------------------------------------------------------------------------
# Prompt adaptation (alternative to translation)
# ---------------------------------------------------------------------------
def adapt_prompt_for_language(
    system_prompt: str,
    lang: str,
    strategy: str = "instruct",
) -> str:
    """
    Adapt a system prompt for non-English input.

    Strategies:
      "instruct" — add a note that the transcript may be in another language
      "bilingual" — instruct the LLM to classify in English regardless of input language
    """
    lang_name = _LANG_NAMES.get(lang, lang)

    if strategy == "bilingual":
        addendum = (
            f"\n\nNOTE: The transcript may be in {lang_name}. "
            f"Regardless of the transcript's language, classify using the "
            f"English taxonomy codes and write all output fields in English."
        )
    else:  # "instruct"
        addendum = (
            f"\n\nNOTE: The transcript is in {lang_name}. "
            f"Read and understand the {lang_name} text, then classify using "
            f"the English taxonomy codes. All output fields should be in English."
        )

    return system_prompt + addendum


# ---------------------------------------------------------------------------
# DataFrame-level preprocessing
# ---------------------------------------------------------------------------
async def preprocess_multilingual(
    df: pd.DataFrame,
    cfg: RunConfig,
    text_col: str = "transcript",
    strategy: str = "translate",
    translate_threshold: float = 0.5,
) -> pd.DataFrame:
    """
    Preprocess a DataFrame for multilingual classification.

    Parameters
    ----------
    df : input DataFrame
    cfg : RunConfig
    text_col : column containing transcript text
    strategy :
        "translate" — translate non-English text to English
        "prompt"    — keep original language, adapt prompts later
        "detect"    — detect only, no transformation
    translate_threshold : minimum language confidence to skip translation

    Returns
    -------
    DataFrame with language columns and optionally translated text.
    """
    # Step 1: Detect languages
    df = detect_language(df, text_col=text_col)

    if strategy == "detect":
        return df

    # Step 2: Group non-English records by language
    non_english = df[df["_detected_language"] != "en"]

    if len(non_english) == 0:
        logger.info("All records are in English — no multilingual preprocessing needed")
        return df

    logger.info(
        "Multilingual preprocessing: %d non-English records (%s strategy)",
        len(non_english), strategy,
    )

    if strategy == "translate":
        # Translate each language group
        df = df.copy()
        df["_original_text"] = ""
        df["_translated_from"] = ""

        for lang, group in non_english.groupby("_detected_language"):
            if lang == "en":
                continue

            logger.info("Translating %d records from %s", len(group), lang)

            records = [
                {"uid": str(row.get("uid", idx)), "text": str(row[text_col])}
                for idx, row in group.iterrows()
            ]

            translated = await translate_batch(records, str(lang), cfg)

            # Map translations back to the DataFrame
            uid_to_translated = {r["uid"]: r for r in translated}
            for idx, row in group.iterrows():
                uid = str(row.get("uid", idx))
                if uid in uid_to_translated:
                    tr = uid_to_translated[uid]
                    df.at[idx, text_col] = tr["text"]
                    df.at[idx, "_original_text"] = tr["_original_text"]
                    df.at[idx, "_translated_from"] = tr["_translated_from"]

    elif strategy == "prompt":
        # No text transformation — prompts will be adapted at classification time
        df["_prompt_language"] = df["_detected_language"].apply(
            lambda x: x if x != "en" else ""
        )

    return df
