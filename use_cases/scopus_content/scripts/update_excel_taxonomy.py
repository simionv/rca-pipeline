"""Update scopus_content_pipeline_definition_v2.xlsx with harmonised policy framework."""
import openpyxl

PATH = r'C:\Users\simionv\custom_taxonomy_v1\definitions\scopus_content_pipeline_definition_v2.xlsx'
wb = openpyxl.load_workbook(PATH)

# ============================================================
# 1. TAXONOMY SHEET
# ============================================================
ws_tax = wb['taxonomy']

# Step 1a: Insert CR1.8 after row 10 (last L2 under "Content coverage & indexing")
ws_tax.insert_rows(11, 1)
r = ws_tax[11]
r[0].value = 'contact_reason'
r[1].value = 'L2'
r[2].value = 'Article-in-Press (AiP) visibility or missing'
r[3].value = (
    "Customer reports their AiP has not appeared in Scopus within the expected "
    "4-day FTP delivery window. Use when customer specifically references AiP, "
    "pre-publication, or accepted manuscript status. Links to policy PA10."
)
r[4].value = 'Links to PA10'
r[5].value = 'CR1.8'
print("Inserted CR1.8 at row 11")

# After CR1.8 insertion rows >= 11 shifted +1:
# PA3 was 100 -> now 101
# PA5 was 102 -> now 103
# PA9 was 106 -> now 107

# Step 1b: Insert 8 rows after new PA9 position (row 107)
ws_tax.insert_rows(108, 8)
new_rows = [
    ('policy_compliance', 'L2',
     'Article-in-Press (AiP) eligibility and processing',
     (
         'AiP items carry unit type ARTICLE-IN-PRESS and status S200. DOI is MANDATORY for all AiP items. '
         'No volume, issue, or page data required. Grant info (grantlist) NOT captured. '
         'Items appear in Scopus within 4 days of publisher FTP delivery, distinct from PA5 standard '
         '2-3 week e-feed timeline. Violation: agent quotes 2-3 week SLA for an AiP query; '
         'agent says DOI optional.'
     ),
     'CAR Manual S5', 'PA10'),
    ('policy_compliance', 'L2',
     'Excluded item types (CAR Manual S1 list)',
     (
         'These item types are NOT indexed: book reviews; obituaries (incl. "In Memoriam"); '
         'advertisements; society news; notices of future conferences/events; reprints published elsewhere; '
         'personal reports; indexes; addendums; product/video/audio reviews; award winner notifications; '
         'interviews; Instructions to Authors; "In this issue" / TOC items. Book reviews and '
         'conference meeting abstracts also covered under PA3. Use PA11 when the customer missing '
         'item falls into one of these specific excluded categories.'
     ),
     'CAR Manual S1', 'PA11'),
    ('policy_compliance', 'L1',
     'Customer root cause',
     'Why the customer demonstrated difficulty understanding or accepting the applicable policy',
     'Merged from policy_understanding module', None),
    ('policy_compliance', 'L2',
     'Confusing policy wording',
     'The policy language is unclear, technical, or ambiguous -- customer confusion is a natural consequence of the wording itself',
     None, 'PU2.1'),
    ('policy_compliance', 'L2',
     'Lack of policy awareness',
     'Customer was simply unaware the policy existed before contacting support',
     None, 'PU2.2'),
    ('policy_compliance', 'L2',
     'Agent explanation issue',
     'Customer understood the policy when it was properly explained -- confusion arose from an unclear or incomplete agent explanation',
     None, 'PU2.3'),
    ('policy_compliance', 'L2',
     'Policy disagreement',
     'Customer understands the policy but disputes whether it should apply to their case',
     None, 'PU2.4'),
    ('policy_compliance', 'L2',
     'Not applicable -- no customer understanding issue',
     None, None, 'PU2.5'),
]
for offset, (mod, lvl, lbl, desc, notes, code) in enumerate(new_rows):
    r = ws_tax[108 + offset]
    r[0].value = mod
    r[1].value = lvl
    r[2].value = lbl
    r[3].value = desc
    r[4].value = notes
    r[5].value = code
print("Inserted 8 rows (PA10, PA11, L1 Customer root cause, PU2.1-PU2.5) at rows 108-115")

# Step 1c: Append cross-references to PA3/PA5/PA9 descriptions
# Rows after CR1.8 insertion only (rows below 108 unaffected by second insertion):
appendages = {
    101: ' -- For the full specific exclusion list (obituaries, ads, reprints, interviews, etc.) see PA11.',
    103: ' -- AiP-specific processing rules (mandatory DOI, no volume/page, no grant info) are classified under PA10, not PA5.',
    107: (
        ' -- Server source IDs: arXiv 923623402, bioRxiv 923623403, ChemRxiv 923623404, '
        'medRxiv 928910002, SSRN 931193761, TechRxiv 937262106, ResearchSquare 937262107 (CAR Manual S6).'
    ),
}
for row_num, appendage in appendages.items():
    cell = ws_tax.cell(row=row_num, column=4)
    cell.value = (cell.value or '') + appendage
    print(f"  Appended cross-ref to row {row_num}")

# ============================================================
# 2. FIELDS SHEET
# ============================================================
ws_fld = wb['fields']

# Insert 2 rows after row 27 (last policy_compliance field: compliance_evidence)
ws_fld.insert_rows(28, 2)

r1 = ws_fld[28]
r1[0].value = 'policy_compliance'
r1[1].value = 'customer_understanding_issue'
r1[2].value = 'enum'
r1[3].value = 'Whether the customer demonstrated difficulty understanding, accepting, or was unaware of the applicable policy.'
r1[4].value = (
    'Set to "yes" if the transcript shows the customer struggling to understand, accept, or was unaware of '
    'the applicable policy. Set to "no" if the customer understood the policy (even if they disagreed), '
    'or if no policy applies.'
)
r1[5].value = True
r1[6].value = False
r1[7].value = 'yes|no'
r1[8].value = None

r2 = ws_fld[29]
r2[0].value = 'policy_compliance'
r2[1].value = 'customer_root_cause_code'
r2[2].value = 'code'
r2[3].value = 'PU2.x code explaining why the customer had difficulty with the applicable policy. Use PU2.5 (not applicable) when customer_understanding_issue is "no".'
r2[4].value = (
    'Select the PU2.x code that best explains WHY the customer had difficulty: '
    'PU2.1 confusing wording; PU2.2 lack of awareness; PU2.3 agent explanation issue; '
    'PU2.4 policy disagreement; PU2.5 not applicable.'
)
r2[5].value = True
r2[6].value = False
r2[7].value = None
r2[8].value = None
print("\nInserted customer_understanding_issue and customer_root_cause_code fields at rows 28-29")

# ============================================================
# 3. MODULES SHEET
# ============================================================
ws_mod = wb['modules']
headers_mod = [cell.value for cell in ws_mod[1]]
enabled_col = headers_mod.index('enabled') + 1
desc_col    = headers_mod.index('description') + 1

# Disable policy_understanding (row 5)
ws_mod.cell(row=5, column=enabled_col).value = False
print("\nSet policy_understanding enabled=FALSE (row 5)")

# Update policy_compliance description (row 6)
current_desc = ws_mod.cell(row=6, column=desc_col).value or ''

old_intro = (
    'Assess whether each Scopus support ticket was handled in accordance with the official '
    'Scopus Content Coverage Policy. Use the policy reference below to make your assessment.'
)
new_intro = (
    'Assess whether each Scopus support ticket was handled in accordance with the official '
    'Scopus Content Coverage Policy (PA1-PA9; Content Coverage Guide) and CAR Creation Manual '
    'rules (PA10 AiP, PA11 excluded item types). For each ticket: identify which policies apply; '
    'assess whether the agent correctly communicated the policy (agent compliance dimension); '
    'assess whether the customer demonstrated difficulty understanding or accepting the applicable '
    'policy (customer understanding dimension, merged from policy_understanding). Both dimensions '
    'use the same PA code as anchor. Use the policy reference below to make your assessment.'
)
updated_desc = current_desc.replace(old_intro, new_intro)
if updated_desc == current_desc:
    print("  WARNING: intro replacement did not match -- check old_intro text")

pa10_pa11 = (
    '\n\nPA10 -- ARTICLE-IN-PRESS (AiP) ELIGIBILITY AND PROCESSING\n'
    'AiP items require a mandatory DOI and are available in Scopus within 4 days of FTP delivery '
    'from the publisher. Records carry unit type ARTICLE-IN-PRESS and status stage S200. No volume, '
    'issue, or page data required. Grant information NOT captured. Violations: agent quotes the '
    '2-3 week standard timeline for an AiP query; agent states DOI is optional. '
    'Source: CAR Creation Manual S5.\n\n'
    'PA11 -- EXCLUDED ITEM TYPES (CAR Manual S1)\n'
    'These item types are NOT indexed: book reviews, obituaries, advertisements, society news, '
    'conference/event notices, reprints published elsewhere, personal reports, indexes, addendums, '
    'product/video/audio reviews, award notifications, interviews, Instructions to Authors, '
    '"In this issue" / TOC items. Violation: agent promises to index one of these items, '
    'or fails to cite this exclusion when declining a request. Source: CAR Creation Manual S1.'
)
updated_desc += pa10_pa11

ws_mod.cell(row=6, column=desc_col).value = updated_desc
print("Updated policy_compliance description (row 6)")

# ============================================================
# SAVE
# ============================================================
wb.save(PATH)
print(f"\nSaved: {PATH}")
print("Done.")
