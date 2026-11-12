"""Tests for rca_pipeline.utils — post-processing helpers, no LLM calls."""
import pandas as pd
import pytest
from rca_pipeline.utils import (
    drop_enrichment_cols,
    normalise_friction_value,
    make_batches,
    merge_results,
    validate_enum_cols,
    _evidence_in_transcript,
    _normalise_for_match,
)
from rca_pipeline.config import RunConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _cfg(**kwargs) -> RunConfig:
    return RunConfig(input_file="test.csv", output_file="out.xlsx", **kwargs)


def _df(*cols, n=5) -> pd.DataFrame:
    data = {c: [f"{c}_{i}" for i in range(n)] for c in cols}
    data.setdefault("uid", [str(i) for i in range(n)])
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# drop_enrichment_cols
# ---------------------------------------------------------------------------

def test_drop_enrichment_cols_removes_known_prefixes(monkeypatch):
    monkeypatch.setattr("rca_pipeline.utils._load_config", lambda: {
        "enrichment_prefixes": ["contact_reason_primary_code"]
    })
    df = pd.DataFrame({
        "uid": ["1"],
        "transcript": ["hello"],
        "contact_reason_primary_code": ["CR1.1"],
        "custom_col": ["keep"],
    })
    result = drop_enrichment_cols(df)
    assert "contact_reason_primary_code" not in result.columns
    assert "custom_col" in result.columns
    assert "uid" in result.columns

def test_drop_enrichment_cols_noop_when_no_enrichment(monkeypatch):
    monkeypatch.setattr("rca_pipeline.utils._load_config", lambda: {})
    df = pd.DataFrame({"uid": ["1"], "text": ["hello"]})
    result = drop_enrichment_cols(df)
    assert list(result.columns) == ["uid", "text"]


# ---------------------------------------------------------------------------
# make_batches
# ---------------------------------------------------------------------------

def test_make_batches_splits_by_size():
    df = pd.DataFrame({"uid": range(10), "text": ["x"] * 10})
    batches = make_batches(df, batch_size=3, max_chars=99999, text_col="text")
    sizes = [len(b) for b in batches]
    assert sum(sizes) == 10
    assert all(s <= 3 for s in sizes)

def test_make_batches_single_record():
    df = pd.DataFrame({"uid": [1], "text": ["hello"]})
    batches = make_batches(df, batch_size=10, max_chars=99999, text_col="text")
    assert len(batches) == 1
    assert len(batches[0]) == 1

def test_make_batches_empty():
    df = pd.DataFrame({"uid": [], "text": []})
    batches = make_batches(df, batch_size=5, max_chars=99999, text_col="text")
    assert batches == []

def test_make_batches_char_limit_splits():
    # Each record is 1000 chars; limit 1500 → max 1 per batch
    df = pd.DataFrame({"uid": range(3), "text": ["a" * 1000] * 3})
    batches = make_batches(df, batch_size=10, max_chars=1500, text_col="text")
    assert len(batches) == 3


# ---------------------------------------------------------------------------
# merge_results
# ---------------------------------------------------------------------------

def test_merge_results_adds_columns():
    df = pd.DataFrame({"uid": ["1", "2"], "text": ["a", "b"]})
    results = [
        {"uid": "1", "contact_reason_primary_code": "CR1.1"},
        {"uid": "2", "contact_reason_primary_code": "CR2.1"},
    ]
    out = merge_results(df, results, id_col="uid")
    assert "contact_reason_primary_code" in out.columns
    assert out.loc[out["uid"] == "1", "contact_reason_primary_code"].iloc[0] == "CR1.1"

def test_merge_results_handles_missing_uid():
    df = pd.DataFrame({"uid": ["1", "2"], "text": ["a", "b"]})
    results = [{"uid": "1", "code": "CR1.1"}]
    out = merge_results(df, results, id_col="uid")
    assert len(out) == 2  # both rows preserved

def test_merge_results_empty_results():
    df = pd.DataFrame({"uid": ["1"], "text": ["a"]})
    out = merge_results(df, [], id_col="uid")
    assert "uid" in out.columns
    assert len(out) == 1


# ---------------------------------------------------------------------------
# validate_enum_cols
# ---------------------------------------------------------------------------

def test_validate_enum_cols_blanks_invalid(monkeypatch):
    monkeypatch.setattr("rca_pipeline.utils._load_config", lambda: {
        "enum_validators": {"effort_score": ["low", "medium", "high"]}
    })
    df = pd.DataFrame({"effort_score": ["low", "INVALID", "medium", None]})
    out = validate_enum_cols(df)
    assert out["effort_score"].iloc[0] == "low"
    assert out["effort_score"].iloc[1] == ""  # blanked
    assert out["effort_score"].iloc[2] == "medium"

def test_validate_enum_cols_case_normalises(monkeypatch):
    monkeypatch.setattr("rca_pipeline.utils._load_config", lambda: {
        "enum_validators": {"effort_score": ["low", "medium", "high"]}
    })
    df = pd.DataFrame({"effort_score": ["LOW", "Medium"]})
    out = validate_enum_cols(df)
    assert out["effort_score"].iloc[0] == "low"
    assert out["effort_score"].iloc[1] == "medium"


# ---------------------------------------------------------------------------
# normalise_friction_value
# ---------------------------------------------------------------------------

def test_normalise_friction_known_keyword(monkeypatch):
    monkeypatch.setattr("rca_pipeline.utils._load_config", lambda: {
        "friction_categories": [
            {"label": "Self-service failure", "keywords": ["portal", "online form"]}
        ]
    })
    result = normalise_friction_value("Had to use the portal again")
    assert result == "Self-service failure"

def test_normalise_friction_no_match(monkeypatch):
    monkeypatch.setattr("rca_pipeline.utils._load_config", lambda: {
        "friction_categories": [
            {"label": "Self-service failure", "keywords": ["portal"]}
        ]
    })
    result = normalise_friction_value("everything was fine")
    assert result == "everything was fine"  # returned unchanged

def test_normalise_friction_empty(monkeypatch):
    monkeypatch.setattr("rca_pipeline.utils._load_config", lambda: {"friction_categories": []})
    assert normalise_friction_value("") == ""
    assert normalise_friction_value(None) == ""


# ---------------------------------------------------------------------------
# Evidence grounding — _normalise_for_match / _evidence_in_transcript
#
# robust_json_loads() rewrites curly quotes to ASCII on every LLM response, so a
# faithfully copied quote reaches this check with different punctuation from the
# transcript. And Tier 2's overlap was measured over whitespace tokens, which
# carries no signal in Chinese or Japanese. Both made honest evidence look
# fabricated.
# ---------------------------------------------------------------------------

CJK_TRANSCRIPT = (
    "Customer: \u4f60\u597d\uff0c\u6211\u65e0\u6cd5\u4e0b\u8f7d\u8fd9\u7bc7\u6587\u7ae0\u3002"
    "Agent: \u8bf7\u60a8\u63d0\u4f9b\u673a\u6784\u540d\u79f0\u3002"
)


def test_normalise_for_match_folds_typographic_quotes():
    assert _normalise_for_match('he said \u201cno access\u201d') == _normalise_for_match(
        'he said "no access"')
    assert _normalise_for_match("the user\u2019s account") == _normalise_for_match(
        "the user's account")


def test_evidence_grounded_when_only_quote_style_differs():
    """Row 260427-011849 from the production probe, which was flagged as a
    hallucination.

    The model copied the phrase faithfully; robust_json_loads() had already
    rewritten the transcript's curly quotes to ASCII by the time the evidence was
    parsed. Tier 1 therefore missed, and with only 5 whitespace tokens the token
    overlap came to 0.40 against a 0.65 threshold.

    Note it takes a short or CJK string to expose this. In a long English
    sentence one mismatched token out of eight still clears the threshold, so
    token overlap masks the problem rather than fixing it.
    """
    transcript = (
        'Customer: \u5173\u4e8e\u8bbf\u95eeScienceDirect\u6570\u636e\u5e93\u53cd\u590d\u51fa\u73b0'
        '\u201cAre you a Robot?\u201d \u8fd9\u4e2a\u9a8c\u8bc1\u9875\u9762\u7684\u95ee\u9898\uff0c'
        '\u8bf7\u5e2e\u5fd9\u5904\u7406\u3002'
    )
    evidence = (
        '\u5173\u4e8e\u8bbf\u95eeScienceDirect\u6570\u636e\u5e93\u53cd\u590d\u51fa\u73b0'
        '"Are you a Robot?" \u8fd9\u4e2a\u9a8c\u8bc1\u9875\u9762\u7684\u95ee\u9898'
    )
    assert _evidence_in_transcript(evidence, transcript)


def test_quote_fold_alone_is_enough_for_long_english():
    """Guards the claim in the test above: a long English sentence whose quotes
    were rewritten was already tolerated by token overlap, so nothing regressed
    for English when the fallback changed."""
    transcript = 'Customer: I keep seeing \u201cAre you a Robot?\u201d on every single page.'
    evidence = 'I keep seeing "Are you a Robot?" on every single page.'
    assert _evidence_in_transcript(evidence, transcript)


def test_evidence_grounded_plain_substring_english():
    transcript = "Customer: Please can I have the full text for the below article."
    assert _evidence_in_transcript("Please can I have the full text", transcript)


def test_cjk_evidence_grounded_exact_substring():
    """Tier 1 — must already have passed before the fix, so this guards a
    regression rather than proving one."""
    evidence = "\u6211\u65e0\u6cd5\u4e0b\u8f7d\u8fd9\u7bc7\u6587\u7ae0"
    assert _evidence_in_transcript(evidence, CJK_TRANSCRIPT)


def test_cjk_evidence_grounded_with_one_character_changed():
    """Tier 2. One character differs, so Tier 1 misses. As a single whitespace
    token this scored 0.0 on token overlap and was flagged; character overlap
    recognises it."""
    evidence = "\u6211\u65e0\u6cd5\u4e0b\u8f7d\u90a3\u7bc7\u6587\u7ae0"
    assert _evidence_in_transcript(evidence, CJK_TRANSCRIPT)


def test_fabricated_english_evidence_still_flagged():
    """The risk in relaxing Tier 2 is that it stops catching anything."""
    transcript = "Customer: Please can I have the full text for the below article."
    assert not _evidence_in_transcript(
        "The customer confirmed they are a patient and paid by credit card", transcript)


def test_fabricated_cjk_evidence_still_flagged():
    """Character overlap must not wave through unrelated CJK text."""
    fabricated = "\u6211\u5df2\u7ecf\u4ed8\u6b3e\u8d2d\u4e70\u4e86\u5e74\u5ea6\u8ba2\u9605\u670d\u52a1"
    assert not _evidence_in_transcript(fabricated, CJK_TRANSCRIPT)


def test_empty_evidence_is_not_flagged():
    assert _evidence_in_transcript("", "anything")
    assert _evidence_in_transcript("something", "")
