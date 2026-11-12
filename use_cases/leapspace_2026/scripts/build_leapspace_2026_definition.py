"""
build_leapspace_2026_definition.py
==================================
Generate `definitions/leapspace_2026_pipeline_definition.xlsx` from the revised
LeapSpace taxonomy in `data/copy_leapspace_enriched.xlsx`.

The source workbook holds the classification guidance that makes this taxonomy
useful -- "Use when", "Strong signals in the ticket", "Do not use as evidence on
its own" for contact reasons, and "Definition / summary" + "Ticket signals /
evidence used for classification" for root causes.  That text is copied
VERBATIM into the taxonomy `description` cells so it reaches the LLM prompt
intact via taxonomy_to_rich_prompt().

Three modules are defined:

  leapspace_contact_reason    LCR   8 L1 groups x 1 L2 leaf   -> all tickets
  leapspace_rc_institutional  RCI   1 L1 + 12 L2 leaves       -> institutional subset
  leapspace_rc_individual     RCU   1 L1 +  9 L2 leaves       -> individual subset

Every taxonomy is 2-level because build_pipeline.py always appends
"CRITICAL: Always use LEAF-level codes (with a dot ...)" to the generated
prompt, so L1-only codes would contradict the instructions.  For the contact
reason module each category is therefore an L1 group with a single L2 leaf
repeating the label; the guidance text sits on the leaf.

Then run:
  python build_pipeline.py build --input definitions/leapspace_2026_pipeline_definition.xlsx \
      --force leapspace_contact_reason leapspace_rc_institutional leapspace_rc_individual
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s | %(message)s")
logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent
SOURCE_XLSX = _ROOT / "data" / "copy_leapspace_enriched.xlsx"
OUT_DEFN    = _ROOT / "definitions" / "leapspace_2026_pipeline_definition.xlsx"

SHEET_CR = "CONTACT REASONS def and signals"
SHEET_RC = "ROOT CAUSES Def and Signals"

CR_INSTITUTIONAL = "Institutional user cannot access"
CR_INDIVIDUAL    = "User not able to access"
CR_INTERNAL      = "Internal staff access"

# ---------------------------------------------------------------------------
# Authored additions
# ---------------------------------------------------------------------------
# Everything below this line is NOT in data/copy_leapspace_enriched.xlsx. It was
# added deliberately; everything else in the taxonomy is copied verbatim.

# 1. An eighth category. The source sheet has no home for general product
#    questions ("how does X work?", "LeapSpace vs Scopus AI"), which would
#    otherwise be forced into "Not enough info".
OTHER_LABEL = "Other / not covered"
OTHER_DESC = (
    "Use when: none of the other categories applies after considering each one "
    "— for example general product questions, feature or how-to questions, "
    "comparisons with other Elsevier products, security or policy queries, or "
    "product feedback. "
    "Do not use as evidence on its own: do not use this as a first resort; only "
    "choose it when no other category genuinely fits."
)

# 2. Strong signals for "Internal staff access". The source sheet leaves that
#    column blank for this one category, and it is the only category defined by
#    WHO is asking rather than by the problem. A smoke test on the 50 labelled
#    tickets recovered it only 2/12 times without these signals: the model read
#    the access problem and answered "Institutional user cannot access".
AUTHORED_CR_SIGNALS = {
    CR_INTERNAL: (
        "A sender on an @elsevier.com or @relx.com address; someone asking on "
        "behalf of a named customer, institution or account rather than about "
        "their own access; a forwarded or internal thread between colleagues; a "
        "request for a demo or test account, a RegID, an entitlement check, "
        "customer-access verification, or sign-in instructions to pass on to a "
        "customer."
    ),
}

# 3. A precedence rule for step 1, appended to the module description so it is
#    stated before the taxonomy. This spells out what the source definition of
#    "Internal staff access" already implies -- "The request comes from an
#    Elsevier employee or internal team" -- which the model otherwise ignored in
#    favour of whatever access problem the ticket described.
CR_PRECEDENCE = (
    "Decide WHO is asking before WHAT they are asking about. If the requester is "
    "an Elsevier employee or an internal team — including when they are asking on "
    "behalf of a customer, institution or account — classify the ticket as "
    f"'{CR_INTERNAL}' whatever the underlying access problem turns out to be. "
    "Only classify into one of the access categories when the person who cannot "
    "get in is the one contacting support."
)

# 4. An evidence threshold for step 2. Several root-cause definitions already
#    require the agent to confirm something explicitly; this states the
#    consequence when that confirmation is absent. Without it the smoke test
#    never chose "Not enough info" (0/3) or "General Troubleshooting steps"
#    (0/2), over-committing to specific causes on thin evidence instead.
RC_EVIDENCE_RULE = (
    "A specific root cause applies only when the signals named in its own Ticket "
    "signals / evidence text are actually present. Several definitions require "
    "the agent to confirm something explicitly; if that confirmation is missing, "
    "that root cause does not apply, however plausible the symptom looks. Do not "
    "infer a specific technical cause from a symptom alone. Where the ticket "
    "shows only generic troubleshooting and never establishes which action "
    "worked, prefer the root cause that describes exactly that situation over "
    "guessing the underlying cause. When the required signals are absent "
    "altogether, use the Not enough info code."
)


# ---------------------------------------------------------------------------
# Cell cleaning
# ---------------------------------------------------------------------------
def clean(value: object) -> str:
    """
    Normalise one source cell to a prompt-ready string.

    The wording is kept verbatim.  The only change is whitespace: surrounding
    whitespace is trimmed and non-breaking spaces (U+00A0, present in the source)
    are converted to ordinary spaces so they render predictably in the prompt.
    Cells that are empty or NaN come back as "".

    Note the source legitimately opens three cells with a curly quote (e.g. the
    signals list starting `"I subscribed", "I purchased", ...`); those quotes are
    balanced and must be preserved.
    """
    if value is None:
        return ""
    text = str(value).replace(" ", " ").strip()
    if text.lower() in ("", "nan", "none"):
        return ""
    return text


def find_col(df: pd.DataFrame, *needles: str) -> str:
    """Locate a column by case-insensitive prefix match (headers contain unicode)."""
    for col in df.columns:
        low = str(col).strip().lower()
        if any(low.startswith(n.lower()) for n in needles):
            return col
    raise KeyError(f"No column matching {needles} in {list(df.columns)}")


def join_parts(*parts: tuple[str, str]) -> str:
    """Join (heading, text) pairs, skipping any with empty text."""
    return " ".join(f"{head}: {body}" for head, body in parts if body)


# ---------------------------------------------------------------------------
# Sheet builders
# ---------------------------------------------------------------------------
def build_taxonomy_rows(cr_df: pd.DataFrame, rc_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    # ── leapspace_contact_reason: 8 L1 groups, one L2 leaf each ─────────────
    c_label  = find_col(cr_df, "contact reason")
    c_use    = find_col(cr_df, "use when")
    c_signal = find_col(cr_df, "strong signals")
    c_avoid  = find_col(cr_df, "do not use")

    for _, row in cr_df.iterrows():
        label = clean(row[c_label])
        if not label:
            continue
        signals = clean(row[c_signal])
        note = ""
        if not signals and label in AUTHORED_CR_SIGNALS:
            signals = AUTHORED_CR_SIGNALS[label]
            note = "strong signals authored, source cell is blank"
            logger.info("  added authored signals for %r", label)
        guidance = join_parts(
            ("Use when", clean(row[c_use])),
            ("Strong signals in the ticket", signals),
            ("Do not use as evidence on its own", clean(row[c_avoid])),
        )
        # L1 description left blank on purpose: the leaf carries the guidance,
        # so the rendered prompt shows each category's text exactly once.
        rows.append({"module_name": "leapspace_contact_reason", "level": "L1",
                     "label": label, "description": "", "notes": ""})
        rows.append({"module_name": "leapspace_contact_reason", "level": "L2",
                     "label": label, "description": guidance, "notes": note})

    rows.append({"module_name": "leapspace_contact_reason", "level": "L1",
                 "label": OTHER_LABEL, "description": "", "notes": "authored, not in source sheet"})
    rows.append({"module_name": "leapspace_contact_reason", "level": "L2",
                 "label": OTHER_LABEL, "description": OTHER_DESC,
                 "notes": "authored, not in source sheet"})

    # ── the two root-cause modules ─────────────────────────────────────────
    r_parent = find_col(rc_df, "contact reason")
    r_label  = find_col(rc_df, "root cause")
    r_defn   = find_col(rc_df, "definition")
    r_signal = find_col(rc_df, "ticket signals")

    for module, parent, context in (
        ("leapspace_rc_institutional", CR_INSTITUTIONAL,
         "Every ticket in this task has already been classified as "
         f"'{CR_INSTITUTIONAL}'. Choose the root cause from this group only."),
        ("leapspace_rc_individual", CR_INDIVIDUAL,
         "Every ticket in this task has already been classified as "
         f"'{CR_INDIVIDUAL}' — an individual or personal subscription. "
         "Choose the root cause from this group only."),
    ):
        rows.append({"module_name": module, "level": "L1", "label": parent,
                     "description": context, "notes": ""})

        subset = rc_df[rc_df[r_parent].apply(clean) == parent]
        if subset.empty:
            logger.error("No root-cause rows found for parent %r", parent)
            sys.exit(1)

        for _, row in subset.iterrows():
            label = clean(row[r_label])
            if not label:
                continue
            rows.append({
                "module_name": module,
                "level": "L2",
                "label": label,
                "description": join_parts(
                    ("Definition", clean(row[r_defn])),
                    ("Ticket signals / evidence", clean(row[r_signal])),
                ),
                "notes": "",
            })

    return pd.DataFrame(rows, columns=["module_name", "level", "label",
                                       "description", "notes"])


def build_modules_sheet() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "module_name": "leapspace_contact_reason",
            "taxonomy_prefix": "LCR",
            "taxonomy_file": "leapspace_contact_reason.json",
            "reorder_group": "A", "reorder_order": 1, "enabled": True,
            "description": (
                "Classify the reason someone contacted support about LeapSpace into "
                "exactly one of eight categories. Each category carries a Use when "
                "definition, the Strong signals to look for, and signals that must not be "
                "treated as evidence on their own. Assign the single best-fitting LEAF "
                "code (e.g. LCR3.1). "
                + CR_PRECEDENCE
            ),
            "notes": "Step 1 of 2. Runs on every ticket.",
        },
        {
            "module_name": "leapspace_rc_institutional",
            "taxonomy_prefix": "RCI",
            "taxonomy_file": "leapspace_rc_institutional.json",
            "reorder_group": "B", "reorder_order": 2, "enabled": True,
            "description": (
                f"Identify the root cause for LeapSpace tickets already classified as "
                f"'{CR_INSTITUTIONAL}'. Each root cause carries a Definition and the "
                "Ticket signals / evidence used for classification -- use these to "
                "separate root causes that look similar. Assign the single best-fitting "
                "LEAF code (e.g. RCI1.4)."
            ),
            "notes": "Step 2a. Runs only on the institutional-access subset.",
        },
        {
            "module_name": "leapspace_rc_individual",
            "taxonomy_prefix": "RCU",
            "taxonomy_file": "leapspace_rc_individual.json",
            "reorder_group": "B", "reorder_order": 3, "enabled": True,
            "description": (
                f"Identify the root cause for LeapSpace tickets already classified as "
                f"'{CR_INDIVIDUAL}' -- an individual or personal subscription. Each root "
                "cause carries a Definition and the Ticket signals / evidence used for "
                "classification -- use these to separate root causes that look similar. "
                "Assign the single best-fitting LEAF code (e.g. RCU1.5)."
            ),
            "notes": "Step 2b. Runs only on the individual-access subset.",
        },
    ])


def build_fields_sheet() -> pd.DataFrame:
    """
    Three fields per module: code, justification, verbatim evidence.

    Field names deliberately avoid the `contact_reason_` / `root_cause_`
    prefixes, which utils._STRUCTURAL_PREFIXES would strip from any re-run
    input via drop_enrichment_cols().
    """
    specs = [
        (
            "leapspace_contact_reason", "lcr",
            "Assign the single leaf-level code (e.g. LCR3.1) for the contact reason that "
            "best matches this ticket. Read the Use when text for each category and weigh "
            "the Strong signals. Never treat something listed under Do not use as evidence "
            "on its own as sufficient evidence by itself. Only use codes from the taxonomy.",
            "In one or two sentences, explain why this contact reason applies and why the "
            "closest alternative category does not. Refer to what the ticket actually "
            "shows. Do not use apostrophes or quotation marks in your answer.",
            "Copy verbatim the single sentence or phrase from the transcript that most "
            "strongly supports this contact reason. Do not paraphrase, infer, or add words "
            "that are not in the transcript. If no direct evidence exists, return an empty "
            "string.",
        ),
        (
            "leapspace_rc_institutional", "rci",
            "Assign the single leaf-level code (e.g. RCI1.4) for the root cause that best "
            "matches this ticket. Match on the Definition and the Ticket signals / evidence "
            "for each root cause, not on surface keywords. Only use codes from the "
            "taxonomy. " + RC_EVIDENCE_RULE,
            "In one or two sentences, explain which ticket signals led to this root cause "
            "and why the most similar alternative root cause does not fit. Do not use "
            "apostrophes or quotation marks in your answer.",
            "Copy verbatim the single sentence or phrase from the transcript that most "
            "strongly supports this root cause. Do not paraphrase, infer, or add words "
            "that are not in the transcript. If no direct evidence exists, return an empty "
            "string.",
        ),
        (
            "leapspace_rc_individual", "rcu",
            "Assign the single leaf-level code (e.g. RCU1.5) for the root cause that best "
            "matches this ticket. Match on the Definition and the Ticket signals / evidence "
            "for each root cause, not on surface keywords. Only use codes from the "
            "taxonomy. " + RC_EVIDENCE_RULE,
            "In one or two sentences, explain which ticket signals led to this root cause "
            "and why the most similar alternative root cause does not fit. Do not use "
            "apostrophes or quotation marks in your answer.",
            "Copy verbatim the single sentence or phrase from the transcript that most "
            "strongly supports this root cause. Do not paraphrase, infer, or add words "
            "that are not in the transcript. If no direct evidence exists, return an empty "
            "string.",
        ),
    ]

    rows: list[dict[str, object]] = []
    for module, stub, code_instr, just_instr, ev_instr in specs:
        rows.append({
            "module_name": module, "field_name": f"{stub}_code", "field_type": "code",
            "description": "Assigned leaf code", "prompt_instruction": code_instr,
            "in_output": True, "explode_list": False, "validate_enum": True, "notes": "",
        })
        rows.append({
            "module_name": module, "field_name": f"{stub}_justification", "field_type": "str",
            "description": "Why this code was chosen over the nearest alternative",
            "prompt_instruction": just_instr,
            "in_output": True, "explode_list": False, "validate_enum": False, "notes": "",
        })
        rows.append({
            "module_name": module, "field_name": f"{stub}_evidence", "field_type": "str",
            "description": "Verbatim supporting quote from the transcript",
            "prompt_instruction": ev_instr,
            "in_output": True, "explode_list": False, "validate_enum": False, "notes": "",
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
def main() -> None:
    if not SOURCE_XLSX.exists():
        logger.error("Source workbook not found: %s", SOURCE_XLSX)
        sys.exit(1)

    logger.info("Reading %s", SOURCE_XLSX.name)
    cr_df = pd.read_excel(SOURCE_XLSX, sheet_name=SHEET_CR, engine="openpyxl")
    rc_df = pd.read_excel(SOURCE_XLSX, sheet_name=SHEET_RC, engine="openpyxl")
    logger.info("  contact reasons: %d rows | root causes: %d rows", len(cr_df), len(rc_df))

    modules_df  = build_modules_sheet()
    fields_df   = build_fields_sheet()
    taxonomy_df = build_taxonomy_rows(cr_df, rc_df)

    # Sanity-check the shape before anything downstream depends on it.
    expected = {"leapspace_contact_reason": (8, 8),
                "leapspace_rc_institutional": (1, 12),
                "leapspace_rc_individual": (1, 9)}
    for module, (want_l1, want_l2) in expected.items():
        sub = taxonomy_df[taxonomy_df["module_name"] == module]
        got_l1 = int((sub["level"] == "L1").sum())
        got_l2 = int((sub["level"] == "L2").sum())
        if (got_l1, got_l2) != (want_l1, want_l2):
            logger.error("%s: expected %d L1 / %d L2, got %d / %d",
                         module, want_l1, want_l2, got_l1, got_l2)
            sys.exit(1)
        logger.info("  %-27s %d L1 / %2d L2  OK", module, got_l1, got_l2)

    missing = taxonomy_df[(taxonomy_df["level"] == "L2")
                          & (taxonomy_df["description"].str.len() == 0)]
    if not missing.empty:
        logger.error("Leaf rows with no guidance text:\n%s",
                     missing[["module_name", "label"]].to_string(index=False))
        sys.exit(1)

    OUT_DEFN.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(str(OUT_DEFN), engine="openpyxl") as writer:
        modules_df.to_excel(writer,  sheet_name="modules",  index=False)
        fields_df.to_excel(writer,   sheet_name="fields",   index=False)
        taxonomy_df.to_excel(writer, sheet_name="taxonomy", index=False)

    logger.info("Written %s  (%d modules, %d fields, %d taxonomy rows)",
                OUT_DEFN.relative_to(_ROOT), len(modules_df), len(fields_df), len(taxonomy_df))
    logger.info("Next: python build_pipeline.py build --input %s \\",
                OUT_DEFN.relative_to(_ROOT).as_posix())
    logger.info("          --force %s", " ".join(modules_df["module_name"]))


if __name__ == "__main__":
    main()
