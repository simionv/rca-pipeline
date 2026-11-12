"""Add the csd_dsat_review module to definitions/csd_2026_pipeline_definition.xlsx.

A structured read of dissatisfied tickets, designed to answer two questions that
the survey poses but does not answer: could the process have been made easier, and
is there something in our reply that made things worse.

The model never sees the CSAT score - if it did it would simply restate it. Field
names are prefixed dr_ because run_pipeline merges module outputs by column name
with no collision check.

Idempotent: re-running replaces the module's rows rather than duplicating them.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
XLSX = BASE / "definitions" / "csd_2026_pipeline_definition.xlsx"
MODULE = "csd_dsat_review"

DESCRIPTION = (
    "You are reviewing a closed Scopus content support ticket in which the customer's "
    "request was refused. Read the whole exchange and answer factually about what "
    "happened. Do not speculate about how the customer felt and do not grade the agent "
    "- describe what was asked, what was answered, and what the exchange shows. Every "
    "judgement must rest on words actually present in the transcript. Where the "
    "transcript does not support an answer, say so rather than inferring one."
)

FIELDS = [
    ("dr_asked_for", "str", "What the customer asked for",
     "In one sentence of at most 25 words, state what the customer wanted, in plain "
     "language and from their point of view."),
    ("dr_we_said", "str", "What the agent told them",
     "In one sentence of at most 25 words, state the substance of the final answer the "
     "agent gave - the actual decision or explanation, not the pleasantries."),
    ("dr_driver",
     "enum:the decision itself,the process,how it was explained,a product limit,cannot tell",
     "What the exchange turned on",
     "Choose exactly ONE of the five allowed values. This field names WHAT THE EXCHANGE "
     "TURNED ON; it never takes the value 'none' and never describes the wording of the "
     "reply - a later field covers that. 'the decision itself' = the customer was told no "
     "and the difficulty is with that decision. 'the process' = getting to the answer was "
     "laborious: repeating themselves, chasing, being passed around. 'how it was "
     "explained' = the answer may have been right but was unclear, contradictory, or "
     "unexplained. 'a product limit' = the request was reasonable but the product or "
     "policy simply cannot do it. 'cannot tell' = the transcript does not show enough."),
    ("dr_easier_how", "str", "The single change that would most have reduced effort",
     "Name the ONE change to how this was handled that would most have reduced the "
     "customer's effort - for example answering the actual question first time, giving "
     "the reason with the refusal, or not asking for information already supplied. If "
     "the handling was already direct and the difficulty was the decision itself, answer "
     "exactly 'nothing - the process was already direct'. Do not invent an improvement "
     "where none is evidenced; that answer is expected on many tickets and is correct."),
    ("dr_response_problem",
     "enum:nothing wrong,no reason given,jargon or template tone,"
     "contradicts earlier message,sent elsewhere to pursue it,no next step offered",
     "What in the reply itself made things worse",
     "Judge the agent's WORDING, not the decision. 'nothing wrong' when the reply "
     "explains the decision clearly and leaves the customer knowing where they stand - "
     "this is a legitimate and common answer. 'no reason given' when a refusal is stated without "
     "explaining why. 'jargon or template tone' when boilerplate or internal terminology "
     "is used that the customer would not follow. 'contradicts earlier message' when the "
     "reply conflicts with something said earlier in the same thread. 'sent elsewhere to "
     "pursue it' when the customer is directed to the publisher, editor or another team "
     "to chase it themselves. 'no next step offered' when the answer closes the matter "
     "without telling the customer what they can do next."),
    ("dr_pending_at_close", "enum:yes,no,unclear",
     "Was something still outstanding when the ticket ended",
     "Answer 'yes' if, at the end of the transcript, something was still awaited - an "
     "escalation, a check with a third party, a promised follow-up, or an unanswered "
     "customer question. Answer 'no' if the matter was concluded, INCLUDING when it was "
     "concluded by a clear refusal. A refusal is a conclusion, not a loose end. Answer "
     "'unclear' if the transcript ends ambiguously. Note a ticket can do both: if the "
     "agent said they would check with a supplier, chase a colleague or come back to the "
     "customer, answer 'yes' even though a refusal was also given."),
    ("dr_redirected_to", "str", "Who the customer was told to contact",
     "If the agent told the customer to take this to someone else, name who - for "
     "example 'the publisher', 'the journal editor', 'their librarian'. If nobody, "
     "return an empty string."),
    ("dr_evidence", "str", "Verbatim quote carrying the judgement",
     "Quote verbatim from the transcript the single sentence that most supports your "
     "answers above. Copy it exactly; do not paraphrase or trim to fit."),
]

sheets = pd.read_excel(XLSX, sheet_name=None)
mods, flds = sheets["modules"], sheets["fields"]
before = (len(mods), len(flds))

mods = mods[mods["module_name"] != MODULE].copy()
flds = flds[flds["module_name"] != MODULE].copy()

module_row = {c: None for c in mods.columns}
module_row.update({
    "module_name": MODULE, "taxonomy_prefix": None, "taxonomy_file": None,
    "reorder_group": "F", "reorder_order": 6, "enabled": True,
    "description": DESCRIPTION,
    "notes": "Structured read of dissatisfied tickets. No taxonomy - all fields are "
             "free text or closed enums.",
})
mods = pd.concat([mods, pd.DataFrame([module_row])[mods.columns]], ignore_index=True)

new = []
for name, ftype, desc, instr in FIELDS:
    row = {c: None for c in flds.columns}
    row.update({"module_name": MODULE, "field_name": name, "field_type": ftype,
                "description": desc, "prompt_instruction": instr, "in_output": True,
                "validate_enum": ftype.startswith("enum:")})
    new.append(row)
flds = pd.concat([flds, pd.DataFrame(new)[flds.columns]], ignore_index=True)

dupes = flds[flds.duplicated("field_name", keep=False)]
assert dupes.empty, f"field name collision:\n{dupes[['module_name', 'field_name']]}"
# Enum options are lower-cased by the generated validator but compared against the
# raw option text, so any capital letter here rejects every answer silently.
for _, r in flds[flds["module_name"] == MODULE].iterrows():
    ft = str(r["field_type"])
    if ft.startswith("enum:"):
        opts = ft[5:].split(",")
        bad = [o for o in opts if o != o.lower()]
        assert not bad, f"{r['field_name']} has non-lowercase enum options: {bad}"

sheets["modules"], sheets["fields"] = mods, flds
with pd.ExcelWriter(XLSX, engine="openpyxl") as xl:
    for name, df in sheets.items():
        df.to_excel(xl, sheet_name=name, index=False)

print(f"modules {before[0]} -> {len(mods)}   fields {before[1]} -> {len(flds)}")
print("modules now:", list(mods["module_name"]))
