"""Tests for rca validate: plain-language checks on a definition workbook."""
import pandas as pd
import pytest

from rca_pipeline.validate import check_definition


def _write(path, modules, fields, taxonomy):
    with pd.ExcelWriter(path) as xw:
        pd.DataFrame(modules).to_excel(xw, sheet_name="modules", index=False)
        pd.DataFrame(fields).to_excel(xw, sheet_name="fields", index=False)
        pd.DataFrame(taxonomy, columns=["module_name", "level", "label", "description"]).to_excel(
            xw, sheet_name="taxonomy", index=False)
    return path


GOOD_MODULE = {"module_name": "contact_reason", "taxonomy_prefix": "CR", "taxonomy_file": "contact_reason.json",
               "enabled": "TRUE", "description": "Why did the customer get in touch?"}
GOOD_FIELD = {"module_name": "contact_reason", "field_name": "cr_code", "field_type": "code",
              "prompt_instruction": "Pick the leaf code.", "in_output": "TRUE"}
GOOD_TAX = [{"module_name": "contact_reason", "level": "L1", "label": "Access", "description": "Access problems"},
            {"module_name": "contact_reason", "level": "L2", "label": "Password reset", "description": "Forgot password"}]


@pytest.fixture
def book(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return lambda **kw: _write(tmp_path / "def.xlsx", kw.get("modules", [GOOD_MODULE]),
                               kw.get("fields", [GOOD_FIELD]), kw.get("taxonomy", GOOD_TAX))


def test_clean_workbook_has_no_findings(book):
    errors, warnings, modules = check_definition(book())
    assert errors == [] and warnings == []
    assert modules["contact_reason"]["enabled"]


def test_missing_sheet_is_an_error(tmp_path):
    path = tmp_path / "def.xlsx"
    pd.DataFrame([GOOD_MODULE]).to_excel(path, sheet_name="modules", index=False)
    errors, _, _ = check_definition(path)
    assert any("no 'fields' sheet" in e for e in errors)


def test_unknown_module_reported_with_excel_row(book):
    bad = dict(GOOD_FIELD, module_name="contact_reasn")
    errors, _, _ = check_definition(book(fields=[GOOD_FIELD, bad]))
    assert any(e.startswith("fields, row 3:") and "contact_reasn" in e for e in errors)


def test_l2_before_l1_is_an_error(book):
    errors, _, _ = check_definition(book(taxonomy=[GOOD_TAX[1], GOOD_TAX[0]]))
    assert any("first category" in e for e in errors)


def test_missing_l2_description_is_a_warning(book):
    tax = [GOOD_TAX[0], dict(GOOD_TAX[1], description=None)]
    errors, warnings, _ = check_definition(book(taxonomy=tax))
    assert errors == []
    assert any("has no description" in w for w in warnings)


def test_code_field_without_taxonomy_is_an_error(book):
    mod = dict(GOOD_MODULE, taxonomy_prefix=None, taxonomy_file=None)
    errors, _, _ = check_definition(book(modules=[mod], taxonomy=[]))
    assert any("code field" in e for e in errors)


def test_guidance_row_is_ignored(book):
    note = {"module_name": "Set enabled=FALSE to switch a module off."}
    errors, warnings, modules = check_definition(book(modules=[note, GOOD_MODULE]))
    assert errors == [] and list(modules) == ["contact_reason"]
