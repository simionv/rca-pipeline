"""Tests that generated system prompts contain no doubled curly braces.

The baked-in JSON output schema used to be escaped with `{` -> `{{` on the
assumption that the prompt was later passed through str.format(). It is not:
_build_system_prompt() concatenates, llm_client uses the system prompt verbatim
and substitutes {records_json} in the user prompt with str.replace(). The
escaping therefore leaked literal `{{` / `}}` into the prompt the LLM sees.
"""
import importlib
import importlib.util
import pathlib

import pytest

from rca_pipeline.build import generate_module_py

# policy_understanding is retired (enabled=FALSE in the only definition that
# mentions it — its fields were merged into policy_compliance). A build never
# regenerates it, so its .py still carries the old escaping.
RETIRED_MODULES = {"policy_understanding"}

# Each use case keeps its own build output in use_cases/<name>/generated/modules
# (gitignored, so these live tests only run where modules have been built).
MODULE_FILES = sorted(pathlib.Path(__file__).resolve().parents[1].glob("use_cases/*/generated/modules/*.py"))


def _module_names():
    return [f"{p.parts[-4]}/{p.stem}" for p in MODULE_FILES
            if not p.stem.startswith("_") and p.stem not in RETIRED_MODULES]


def _load(name):
    use_case, stem = name.split("/")
    path = next(p for p in MODULE_FILES if p.parts[-4] == use_case and p.stem == stem)
    spec = importlib.util.spec_from_file_location(f"_probe_{use_case}_{stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _system_prompt(mod):
    """Return the module's system prompt, with a marker for the runtime taxonomy."""
    if hasattr(mod, "_build_system_prompt"):
        return mod._build_system_prompt("<<TAXONOMY>>")
    return mod._SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Generator-level: catches a regression even if nobody regenerates
# ---------------------------------------------------------------------------

_MODULE_ROW = {
    "module_name":     "brace_probe",
    "taxonomy_prefix": "BP",
    "taxonomy_file":   "brace_probe.json",
    "description":     "Probe module for brace escaping.",
}
# a list field with explode_keys is the only field type that emits nested
# braces in the schema, so it is the strongest case for the escaping bug
_FIELDS = [
    {"field_name": "bp_code",    "field_type": "code",
     "prompt_instruction": "Assign a code."},
    {"field_name": "bp_matches", "field_type": "list",
     "explode_keys": "code, verdict", "prompt_instruction": "List matches."},
    {"field_name": "bp_kind",    "field_type": "enum:alpha,beta",
     "prompt_instruction": "Pick a kind."},
]


@pytest.mark.parametrize("has_taxonomy", [True, False])
def test_generated_source_has_no_doubled_braces(has_taxonomy):
    code = generate_module_py(_MODULE_ROW, _FIELDS, has_taxonomy=has_taxonomy)
    # {{records_json}} in the template is an f-string escape and must emit a
    # single-braced placeholder; nothing else may be doubled.
    assert "{records_json}" in code
    assert "{{" not in code
    assert "}}" not in code


def test_generated_source_schema_is_single_braced():
    code = generate_module_py(_MODULE_ROW, _FIELDS, has_taxonomy=True)
    assert '"uid": "<record uid>"' in code
    assert '[{"code": "<code>", "verdict": "<verdict>"}]' in code


# ---------------------------------------------------------------------------
# Live modules: the prompt actually sent to the LLM
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", _module_names())
def test_live_system_prompt_has_no_doubled_braces(name):
    mod = _load(name)
    prompt = _system_prompt(mod)
    assert "{{" not in prompt, f"{name}: doubled '{{{{' in system prompt"
    assert "}}" not in prompt, f"{name}: doubled '}}}}' in system prompt"


@pytest.mark.parametrize("name", _module_names())
def test_live_system_prompt_braces_balanced(name):
    mod = _load(name)
    prompt = _system_prompt(mod)
    assert prompt.count("{") == prompt.count("}"), f"{name}: unbalanced braces"


@pytest.mark.parametrize("name", _module_names())
def test_live_user_prompt_keeps_records_json_placeholder(name):
    # llm_client substitutes this with str.replace — a doubled brace would
    # silently leave the transcripts out of the prompt entirely.
    mod = _load(name)
    assert "{records_json}" in mod._USER_PROMPT_TEMPLATE
