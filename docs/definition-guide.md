# Editing a definition workbook — a guide for non-technical editors

Every analysis ("use case") has one Excel workbook that tells the AI **which questions to answer**
about each support ticket and **which categories it may choose from**. You do not need to write code to
change it. This guide walks you through the common edits.

You will need: Excel, the use-case folder (for example `use_cases/sd_2026/`), and someone (or a
terminal) to run two short commands at the end.

---

## 1. Open the workbook

The workbook is in the use case's `definitions/` folder, for example:

```
use_cases/sd_2026/definitions/sd_2026_pipeline_definition.xlsx
```

There is normally only one workbook in that folder. Don't keep copies there — save backups elsewhere
(the `history/` folder), otherwise the tools won't know which one to use.

## 2. Read the "Start here" sheet

The first sheet explains the workbook in plain words and ends with a table of the steps it contains (example, shortened):

| module | on? | output columns | categories | what it does |
|---|---|---|---|---|
| sd_contact_reason | yes | 3 | 13 | Classify why the customer contacted ScienceDirect support … |
| sd_rc_login | yes | 3 | 9 | Identify the root cause for tickets already classified as 'Login issues' … |

The three sheets you edit:

| Sheet | One row per… | Example |
|---|---|---|
| **modules** | step the AI performs | "contact reason", "root cause for login issues" |
| **fields** | answer (column) a step produces, with the instruction the AI follows | `sdli_code`, `sdli_justification`, `sdli_evidence` |
| **taxonomy** | group (L1) or category (L2) the AI can choose | L1 "Login issues" → L2 "Browser compatibility issues" |

**Hover over any column header** to see a note explaining it.

## 3. The colour convention

The header cells are coloured:

| Colour | Meaning | Examples |
|---|---|---|
| **green** | Edit freely. | `description`, `label`, `prompt_instruction`, `enabled`, `notes`, `level` |
| **yellow** | Advanced — change only if you know what it does. | `taxonomy_prefix`, `field_type`, `in_output`, `explode_list`, `code` |
| **grey** | Linking names — they connect the sheets. If you rename one, rename it everywhere it appears. | `module_name`, `field_name`, `taxonomy_file` |

Other visual hints on the **taxonomy** sheet:

- **L1 rows** (groups) are shaded blue and bold.
- An **L2 row with an empty description** is highlighted amber — fill it in.
- Dropdowns only allow valid values (TRUE/FALSE, L1/L2, field types, module names that exist).

## 4. Common tasks

### 4.1 Add a category

On the **taxonomy** sheet, find the group (L1 row) the new category belongs to and add an L2 row **at
the end of that group**, just above the next L1 row:

```
 module_name   level  label                              description
 ───────────   ─────  ─────────────────────────────────  ───────────────────────────────────────────
 sd_rc_login   L1     Login issues                       Every ticket here is already a login issue…
 sd_rc_login   L2     Entitlement issues                 Definition: Use when the user can identify…
 sd_rc_login   L2     Browser compatibility issues       Definition: Use when login fails only in a…
 sd_rc_login   L2     Two-factor code not received   ◄── NEW ROW: fill module_name, level, label,
                                                           description
 sd_rc_login   L2     Not enough info                    Definition: Use when the user cannot log in…
 sd_rc_login   L2     Other                              Definition: Use for another login issue…
```

Rules of thumb:

- Fill `module_name` (pick from the dropdown), set `level` to **L2**, write the `label` and a
  `description`.
- **Keep "Other" (and "Not enough info") last** in the group, as above.
- **Never type a code.** Codes such as `SDLI1.3` are numbered automatically from the row order. Leave
  the `code` column empty.
- Inserting a row in the middle changes the codes of the rows below it. That is fine for a new
  analysis, but if the use case has already been run, note it in the Change log — earlier results,
  gold-set mappings and stored corrections use the old codes.

To add a whole new group, add an **L1** row followed by at least one L2 row.

### 4.2 Sharpen a description

The `description` of an L2 category is the best way to improve accuracy. It tells the AI when to use
the category — and when not to. Use this pattern:

> **Definition:** Use when *[what the ticket shows]*. Do not use for *[the look-alike case]* — use
> *[the other category]* instead.

| Before | After |
|---|---|
| Browser problems. | Definition: Use when login fails only in a specific browser, device or browser version. Do not use when the user is blocked in every browser — use "Entitlement issues" or "Account locked". |
| Refunds. | Definition: Use when the customer asks for money back. Do not use for questions about a price or an invoice copy — use "Invoice request". |

Tips:

- Write about what the **ticket** shows, not about internal processes the AI can't see.
- Name the nearest look-alike category and say how to tell them apart.
- If experts gave you definitions, paste them word for word, and add your own rules in a separate
  sentence.

The same applies to the module `description` (the AI's overall task) and to each field's
`prompt_instruction` (what exactly to write in that answer).

### 4.3 Switch a step off

On the **modules** sheet, set `enabled` to **FALSE** for that row. The step is skipped from the next
build on; nothing is deleted, and you can switch it back on with TRUE.

```
 module_name           enabled   description
 ────────────────────  ───────   ─────────────────────────────────
 sd_contact_reason     TRUE      Classify why the customer …
 sd_rc_download_config FALSE ◄── switched off
```

### 4.4 Record the change in the Change log

Every edit gets one row on the **Change log** sheet (example rows):

| date | who | sheet | what changed | why |
|---|---|---|---|---|
| 2026-11-12 | your initials | taxonomy | Added L2 "Two-factor code not received" under Login issues | 4% of login tickets in the October sample were about missing codes |
| 2026-11-12 | your initials | taxonomy | Sharpened "Browser compatibility issues" definition | Confused with Entitlement issues in the smoke test |

Then **save and close** the workbook (the tools cannot read it while Excel has it open).

### 4.5 Things to leave alone unless you are sure

- Renaming anything in a **grey** column (it must then be changed on every sheet).
- **Yellow** columns: `taxonomy_prefix`, `field_type`, `in_output`, `explode_list`, `validate_enum`,
  `explode_keys`, `code`, `reorder_group`, `reorder_order`, `discovery_mode`, `extract_prompt`.
- Adding or removing **fields** (output columns) — ask whoever runs the analysis, because notebooks
  and reports may expect them.
- Allowed values in a field type such as `enum:yes,no,unclear` must be written in **lowercase**.

## 5. Check and rebuild

Open a terminal **in the use-case folder** (or ask someone to) and run:

```bash
rca validate      # checks the workbook and explains any problem in plain words
rca build         # turns the workbook into the files the pipeline runs (checks first)
```

`rca build` runs the same check as `rca validate` first and refuses to build if there are errors.

If you changed a module `description` or a field `prompt_instruction`, the person running the analysis
should rebuild that step with `rca build --force <module_name>` — those texts are copied into the step
when it is first built and are only refreshed when forced. (Category labels and descriptions are picked
up by a normal `rca build`.)

## 6. What a clean result looks like

```
$ rca validate
WARNING  taxonomy, row 34: L2 'Two-factor code not received' (sd_rc_login) has no description — add one to improve accuracy.

sd_2026_pipeline_definition.xlsx: OK — no errors, 1 warning(s).
```

- `OK — no errors` means the workbook can be built.
- Warnings don't stop the build, but each one is worth a look.

## 7. Reading `rca validate` messages

Each message starts with **ERROR** or **WARNING**, then the **sheet** and the **Excel row number**,
so you can go straight to the cell.

```
ERROR    taxonomy, row 12: level must be L1 (group) or L2 (category), not 'l3'.
└─┬──┘   └───┬───┘ └──┬─┘  └──────────────────────────┬──────────────────────┘
  │          │        │                               └ what is wrong and how to fix it
  │          │        └ Excel row number
  │          └ sheet
  └ ERROR = must fix before building · WARNING = works, but worth fixing
```

At the end: `<file>: N error(s), M warning(s). Fix the errors, save, and run again.`

### Errors (must fix)

| Message (shortened) | What it means | What to do |
|---|---|---|
| The workbook has no 'taxonomy' sheet | A required sheet was renamed or deleted. | Restore the `modules`, `fields` and `taxonomy` sheets. |
| Sheet 'fields' is missing the column(s): … | A header in row 1 was renamed or deleted. | Restore the header text exactly. |
| Cannot open … Is it still open in Excel? | Excel has the file locked. | Close Excel and run again. |
| module name '…' may only use letters, numbers and _ | A space or symbol in a module name. | Use e.g. `login_root_cause`. |
| module '…' is listed twice | Two rows with the same module name. | Rename or delete one. |
| has a taxonomy_prefix or a taxonomy_file but not both | One of the pair is empty. | Fill both, or clear both if the step has no categories. |
| module '…' is not on the modules sheet. Check the spelling. | A row on `fields` or `taxonomy` points to a module that doesn't exist. | Fix the spelling (use the dropdown). |
| field name '…' may only use letters, numbers and _ | A space or symbol in a field name. | Rename, e.g. `cr_code`. |
| '…' is an enum with fewer than two values | A choice list with only one option. | Write it like `enum:yes,no,unclear`. |
| '…' is a code field, but module '…' has no category list | A `code` answer in a step without categories. | Add the prefix and file on `modules`, or change the field type. |
| level must be L1 (group) or L2 (category) | A typo in the level column. | Choose L1 or L2 from the dropdown. |
| the first category of '…' is L2 | A category before any group. | Add an L1 group row above it. |
| an L2 row of '…' has no label | A category without a name. | Fill the `label`. |
| profile …: not valid JSON | A run profile file is broken. | Ask the analyst; profiles are not edited in Excel. |

### Warnings (worth fixing)

| Message (shortened) | What it means | What to do |
|---|---|---|
| L2 '…' has no description — add one to improve accuracy | Amber cell on the taxonomy sheet. | Write a definition ([4.2](#42-sharpen-a-description)). |
| group '…' has no L2 categories under it | An L1 row with nothing below. | Add categories or delete the group. |
| '…' appears twice in '…' | Duplicate category label in one step. | Merge or rename. |
| '…' has no description. The description is the AI's task | A step without a task. | Describe the step in plain words. |
| '…' has no prompt_instruction | The AI must guess what to write in that column. | Write the instruction. |
| field '…' is used twice | Two answers would write to the same column. | Rename one (ask the analyst). |
| field type '…' is not recognised | Typo in `field_type`; treated as free text. | Use the dropdown. |
| column … should be TRUE or FALSE | Something else typed in a switch column. | Choose TRUE or FALSE. |
| module '…' has categories but no taxonomy_prefix / taxonomy_file | Categories that will be ignored. | Ask the analyst. |
| '…' has a category list but no field of type 'code' | Categories exist but no answer uses them. | Ask the analyst. |
| uses the category list …, but the taxonomy sheet has no rows for it | The step expects categories that don't exist. | Add categories, or ask the analyst. |
| profile …: module(s) … are not enabled | A run profile uses a step you switched off. | Fine if intended; tell the analyst. |
| profile …: input file '…' not found | Normal before an earlier step has run. | Usually nothing to do. |

## 8. Quick checklist

1. Open the workbook in `definitions/`; read **Start here**.
2. Edit **green** columns; leave **yellow** and **grey** to the analyst unless you are sure.
3. New categories: L2 rows at the end of their group, "Other" last, no codes typed.
4. Descriptions: "Definition: Use when … Do not use for …".
5. Switch a step off with `enabled` = FALSE.
6. Add a row to the **Change log**. Save and close.
7. `rca validate`, then `rca build`.

For the full reference of every column, see the [manual](manual.md#3-the-definition-workbook).
