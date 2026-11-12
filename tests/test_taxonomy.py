"""Tests for rca_pipeline.taxonomy — pure functions, no LLM calls, no disk I/O."""
import pytest
from rca_pipeline.taxonomy import (
    flatten_taxonomy,
    get_l1_from_code,
    get_prefix_from_code,
    leaf_label_lookup,
    leaf_description_lookup,
    taxonomy_to_rich_prompt,
    _sort_key,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_TAX = {
    "CR1": {
        "label": "Authentication",
        "children": {
            "CR1.1": {"label": "Login blocked",  "description": "Cannot sign in"},
            "CR1.2": {"label": "Password reset", "description": "Forgot password"},
        },
    },
    "CR2": {
        "label": "Access",
        "children": {
            "CR2.1": {"label": "Permissions", "description": "Insufficient rights"},
        },
    },
}

MULTI_TAX = {
    "contact_reason": SIMPLE_TAX,
    "customer_effort": {
        "CE1": {
            "label": "High effort",
            "children": {
                "CE1.1": {"label": "Repeated explanation"},
            },
        }
    },
}


# ---------------------------------------------------------------------------
# get_l1_from_code
# ---------------------------------------------------------------------------

def test_get_l1_from_code_leaf():
    assert get_l1_from_code("CR1.2") == "CR1"

def test_get_l1_from_code_already_l1():
    assert get_l1_from_code("CR1") == "CR1"

def test_get_l1_from_code_empty():
    assert get_l1_from_code("") == ""

def test_get_l1_from_code_none():
    assert get_l1_from_code(None) == ""


# ---------------------------------------------------------------------------
# get_prefix_from_code
# ---------------------------------------------------------------------------

def test_get_prefix_from_code_cr():
    assert get_prefix_from_code("CR1.2") == "CR"

def test_get_prefix_from_code_ce():
    assert get_prefix_from_code("CE10.3") == "CE"

def test_get_prefix_from_code_empty():
    assert get_prefix_from_code("") == ""


# ---------------------------------------------------------------------------
# _sort_key
# ---------------------------------------------------------------------------

def test_sort_key_ordering():
    codes = ["CR2.1", "CR1.2", "CR1.1", "CR10.1"]
    assert sorted(codes, key=_sort_key) == ["CR1.1", "CR1.2", "CR2.1", "CR10.1"]

def test_sort_key_l1_before_l2():
    assert _sort_key("CR1") < _sort_key("CR1.1")


# ---------------------------------------------------------------------------
# flatten_taxonomy
# ---------------------------------------------------------------------------

def test_flatten_includes_l1_and_l2():
    flat = flatten_taxonomy(SIMPLE_TAX)
    assert flat["CR1"] == "Authentication"
    assert flat["CR1.1"] == "Login blocked"
    assert flat["CR2.1"] == "Permissions"

def test_flatten_empty():
    assert flatten_taxonomy({}) == {}


# ---------------------------------------------------------------------------
# leaf_label_lookup
# ---------------------------------------------------------------------------

def test_leaf_label_lookup_no_config(monkeypatch):
    # Without pipeline_config.json, prefix_map returns {}
    monkeypatch.setattr(
        "rca_pipeline.taxonomy._load_config", lambda: {}
    )
    lookup = leaf_label_lookup({"contact_reason": SIMPLE_TAX})
    assert lookup["CR1.1"] == "Login blocked"
    assert lookup["CR2"] == "Access"

def test_leaf_label_lookup_empty_taxonomy(monkeypatch):
    monkeypatch.setattr("rca_pipeline.taxonomy._load_config", lambda: {})
    lookup = leaf_label_lookup({"contact_reason": {}})
    assert lookup == {}


# ---------------------------------------------------------------------------
# leaf_description_lookup
# ---------------------------------------------------------------------------

def test_leaf_description_lookup(monkeypatch):
    monkeypatch.setattr("rca_pipeline.taxonomy._load_config", lambda: {})
    desc = leaf_description_lookup({"contact_reason": SIMPLE_TAX})
    assert desc["CR1.1"] == "Cannot sign in"
    assert desc["CR1.2"] == "Forgot password"
    assert "CR1" not in desc  # L1 has no description

def test_leaf_description_lookup_missing_descriptions(monkeypatch):
    monkeypatch.setattr("rca_pipeline.taxonomy._load_config", lambda: {})
    tax = {"CR1": {"label": "Auth", "children": {"CR1.1": {"label": "Login"}}}}
    desc = leaf_description_lookup({"x": tax})
    assert desc == {}


# ---------------------------------------------------------------------------
# taxonomy_to_rich_prompt
# ---------------------------------------------------------------------------

def test_rich_prompt_contains_labels():
    prompt = taxonomy_to_rich_prompt(SIMPLE_TAX)
    assert "Authentication" in prompt
    assert "Login blocked" in prompt
    assert "Cannot sign in" in prompt

def test_rich_prompt_sorted():
    prompt = taxonomy_to_rich_prompt(SIMPLE_TAX)
    pos_cr1 = prompt.index("CR1")
    pos_cr2 = prompt.index("CR2")
    assert pos_cr1 < pos_cr2

def test_rich_prompt_empty():
    assert taxonomy_to_rich_prompt({}) == ""
