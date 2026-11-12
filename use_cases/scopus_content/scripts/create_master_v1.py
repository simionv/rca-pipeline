"""
Copy scopus_effort_master.R -> scopus_effort_master_v1.R with:
  - Three-source join: raw_pol_new (Scopus_Content_Policy_enriched.xlsx, has
    PA10/PA11 + customer_understanding_issue + customer_root_cause_*) and
    raw_pol_old (Scopus_Content_Collapsed_compliance_enriched.xlsx, has
    policy_type_* + evidence_1-3 from old policy_understanding module run).
  - root_cause remapped to customer_root_cause_label (PU2.x from new module).
  - Block 8H added (language x policy understanding, guarded -- no lang col yet).

Changes:
  1. Version header at top
  2. Three data sources (raw_pol_old + raw_pol_new)        (~line 95)
  3. pol_cols (new file) + old_cols (old file)             (lines 97-108)
  4. Two-step join                                         (line 112)
  5. Simplified fill-missing block                         (~line 115)
  6a. confused + customer_root_cause in df mutate          (~line 151)
  6b. root_cause remapped to customer_root_cause_label     (~line 153)
  7. ev1_ok guard                                          (line 2065)
  8. Block 8H before PART 9                                (~line 5360)
"""
import re
from pathlib import Path

SRC  = Path(r"C:\Users\simionv\custom_taxonomy_v1\runs\output\Scopus effort\scopus_effort_master.R")
DEST = Path(r"C:\Users\simionv\custom_taxonomy_v1\runs\output\Scopus effort\scopus_effort_master_v1.R")

with open(SRC, encoding="utf-8") as f:
    txt = f.read()

changes = []

# ── 1. Version header ─────────────────────────────────────────────────────────
OLD1 = (
    "# ============================================================================ #\n"
    "#  SCOPUS CUSTOMER EFFORT - MASTER ANALYSIS                                    #\n"
)
NEW1 = (
    "# scopus_effort_master_v1.R -- versioned copy (original: scopus_effort_master.R)\n"
    "# Three-source join: raw_pol_new=Scopus_Content_Policy_enriched.xlsx (PA10/PA11,\n"
    "#   customer_understanding_issue, customer_root_cause_*) + raw_pol_old=\n"
    "#   Scopus_Content_Collapsed_compliance_enriched.xlsx (policy_type_*, evidence_1-3).\n"
    "# root_cause remapped to customer_root_cause_label (PU2.x). Block 8H added (guarded).\n"
    "# ============================================================================ #\n"
    "#  SCOPUS CUSTOMER EFFORT - MASTER ANALYSIS                                    #\n"
)
assert OLD1 in txt, f"Header anchor not found. First 200 chars: {txt[:200]!r}"
txt = txt.replace(OLD1, NEW1, 1)
changes.append("1. Version header updated (three-source join + Block 8H)")

# ── 2. Three data sources ─────────────────────────────────────────────────────
OLD2 = 'raw_pol <- read_excel("Scopus_Content_Collapsed_compliance_enriched.xlsx")'
NEW2 = (
    'raw_pol_old <- read_excel("Scopus_Content_Collapsed_compliance_enriched.xlsx")\n'
    'raw_pol_new <- read_excel("../Scopus_Content_Policy_enriched.xlsx")'
)
assert OLD2 in txt, "raw_pol read_excel line not found"
txt = txt.replace(OLD2, NEW2, 1)
changes.append("2. Three data sources (raw_pol_old + raw_pol_new)")

# ── 3. pol_cols (new file) + old_cols (old file) ──────────────────────────────
OLD3 = '''\
pol_cols <- c(
  "agent_response_compliance",
  "root_cause_code", "root_cause_label", "root_cause_description",
  "evidence_1", "evidence_2", "evidence_3",
  "applicable_policy_codes_1", "applicable_policy_codes_2", "applicable_policy_codes_3",
  "applicable_policy_labels_1", "applicable_policy_labels_2", "applicable_policy_labels_3",
  "policy_type_code", "policy_type_label", "policy_type_description",
  "violation_type_code", "violation_type_label", "violation_type_description",
  "compliance_evidence_1", "compliance_evidence_2", "compliance_evidence_3",
  "compliance_evidence_grounded",
  "confidence", "policy_gap", "policy_too_strict", "policy_understanding_issue"
)'''
NEW3 = '''\
pol_cols <- c(
  "agent_response_compliance",
  "applicable_policy_codes_1", "applicable_policy_codes_2", "applicable_policy_codes_3",
  "applicable_policy_codes_4", "applicable_policy_codes_5",
  "applicable_policy_labels_1", "applicable_policy_labels_2", "applicable_policy_labels_3",
  "applicable_policy_labels_4", "applicable_policy_labels_5",
  "violation_type_code", "violation_type_label", "violation_type_description",
  "compliance_evidence_1", "compliance_evidence_2", "compliance_evidence_3",
  "compliance_evidence_4", "compliance_evidence_5",
  "compliance_evidence_grounded",
  "confidence", "policy_gap", "policy_too_strict",
  "customer_understanding_issue",    # replaces policy_understanding_issue
  "customer_root_cause_code",        # NEW -- PU2.x code
  "customer_root_cause_label",       # NEW -- PU2.x label
  "content_domain"                   # NEW
)

old_cols <- c(
  "policy_type_code", "policy_type_label", "policy_type_description",
  "evidence_1", "evidence_2", "evidence_3",
  "policy_understanding_issue"
)'''
assert OLD3 in txt, "pol_cols vector not found"
txt = txt.replace(OLD3, NEW3, 1)
changes.append("3. pol_cols updated + old_cols added")

# ── 4. Two-step join ──────────────────────────────────────────────────────────
OLD4 = 'left_join(raw_pol |> select(uid, all_of(pol_cols)), by = "uid")'
NEW4 = (
    'left_join(raw_pol_new |> select(uid, any_of(pol_cols)), by = "uid") |>\n'
    '  left_join(raw_pol_old |> select(uid, any_of(old_cols)), by = "uid")'
)
assert OLD4 in txt, "all_of(pol_cols) join line not found"
txt = txt.replace(OLD4, NEW4, 1)
changes.append("4. Two-step join (raw_pol_new then raw_pol_old)")

# ── 5. Simplified fill-missing block ──────────────────────────────────────────
OLD5 = (
    'stopifnot(nrow(raw) == nrow(raw_eff))\n'
    'cat(sprintf("  Joined: %d tickets x %d columns (1:1 on uid)\\n", nrow(raw), ncol(raw)))'
)
NEW5 = (
    'stopifnot(nrow(raw) == nrow(raw_eff))\n'
    'cat(sprintf("  Joined: %d tickets x %d columns (1:1 on uid)\\n", nrow(raw), ncol(raw)))\n'
    '\n'
    '# Raw columns from disabled policy_understanding module;\n'
    '# absent from BOTH source files -- fill so downstream code does not error.\n'
    'absent_fill <- c("root_cause_code", "root_cause_label", "root_cause_description")\n'
    'absent_found <- absent_fill[!absent_fill %in% names(raw)]\n'
    'if (length(absent_found) > 0) {\n'
    '  raw[absent_found] <- NA_character_\n'
    '  cat(sprintf("  NOTE: %d col(s) absent -> filled NA: %s\\n",\n'
    '              length(absent_found), paste(absent_found, collapse = ", ")))\n'
    '}'
)
assert OLD5 in txt, "stopifnot/cat block not found"
txt = txt.replace(OLD5, NEW5, 1)
changes.append("5. fill-missing simplified (only root_cause_* from disabled module)")

# ── 6a. confused mapping + customer_root_cause ────────────────────────────────
OLD6a = '    confused    = policy_understanding_issue == "yes",'
NEW6a = (
    '    confused            = customer_understanding_issue == "yes",\n'
    '    customer_root_cause = as.character(customer_root_cause_label),'
)
assert OLD6a in txt, "confused mapping line not found"
txt = txt.replace(OLD6a, NEW6a, 1)
changes.append("6a. confused mapping updated + customer_root_cause added")

# ── 6b. root_cause remapped to customer_root_cause_label ──────────────────────
OLD6b = '    root_cause  = as.character(root_cause_label),'
NEW6b = '    root_cause  = as.character(customer_root_cause_label),  # PU2.x from new module'
assert OLD6b in txt, "root_cause mapping line not found"
txt = txt.replace(OLD6b, NEW6b, 1)
changes.append("6b. root_cause remapped to customer_root_cause_label")

# ── 7. ev1_ok guard ───────────────────────────────────────────────────────────
OLD7 = 'df$ev1_ok <- verify_quote("evidence_1")          # customer verbatim (confusion)'
NEW7 = (
    '# evidence_1 arrives via raw_pol_old join; guard for partial uid overlap\n'
    'if ("evidence_1" %in% names(df)) {\n'
    '  df$ev1_ok <- verify_quote("evidence_1")          # customer verbatim (confusion)\n'
    '} else {\n'
    '  df$ev1_ok <- FALSE\n'
    '  cat("  NOTE: evidence_1 absent -- ev1_ok set FALSE; customer evidence panels empty.\\n")\n'
    '}'
)
assert OLD7 in txt, "ev1_ok line not found"
txt = txt.replace(OLD7, NEW7, 1)
changes.append("7. ev1_ok guard added")

# ── 8. Block 8H before PART 9 ─────────────────────────────────────────────────
OLD8 = (
    'cat("  NOTE: Block 8D (AiP) enabled after re-classifying with updated policy_compliance module.\\n\\n")\n'
    '\n'
    '\n'
    '# ============================================================================ #\n'
    '# PART 9 - CONSOLE MEGA-SUMMARY                                                #\n'
)
NEW8 = (
    'cat("  NOTE: Block 8D (AiP) enabled after re-classifying with updated policy_compliance module.\\n")\n'
    'cat("  Block 8H [language x policy]: tbl_p8_language_policy.csv + chart_p8_language_policy.png\\n\\n")\n'
    '\n'
    '\n'
    '# ============================================================\n'
    '# 8H. LANGUAGE x POLICY UNDERSTANDING (Q11)\n'
    '# ============================================================\n'
    'cat("8H: Language x policy understanding -----------------------------------------\\n")\n'
    '\n'
    'lang_col <- intersect(\n'
    '  c("language_code", "detected_language", "Language", "contact_language", "lang"),\n'
    '  names(df)\n'
    ')[1]\n'
    '\n'
    'if (!is.na(lang_col)) {\n'
    '  p8h_lang <- df |>\n'
    '    filter(!is.na(.data[[lang_col]]),\n'
    '           !is.na(policy_area), !str_starts(policy_area, "No applicable"),\n'
    '           !is.na(confused)) |>\n'
    '    mutate(non_english = .data[[lang_col]] != "en") |>\n'
    '    group_by(policy_area, non_english) |>\n'
    '    summarise(\n'
    '      n             = n(),\n'
    '      confused_pct  = round(mean(confused,  na.rm = TRUE) * 100, 1),\n'
    '      llm_high_pct  = round(mean(llm_high,  na.rm = TRUE) * 100, 1),\n'
    '      ces_hard3_pct = round(mean(ces_hard3[year == 2025], na.rm = TRUE) * 100, 1),\n'
    '      .groups = "drop"\n'
    '    )\n'
    '\n'
    '  cat(sprintf("  8H: %d rows with language data\\n", sum(!is.na(df[[lang_col]]))))\n'
    '  save_tbl(p8h_lang, "tbl_p8_language_policy.csv")\n'
    '\n'
    '  p_8h <- ggplot(p8h_lang |> filter(n >= 5),\n'
    '    aes(x = reorder(policy_area, -confused_pct), y = confused_pct,\n'
    '        fill = non_english)) +\n'
    '    geom_col(position = "dodge") +\n'
    '    scale_fill_manual(\n'
    '      values = c(`FALSE` = "#3B82F6", `TRUE` = "#EF4444"),\n'
    '      labels = c(`FALSE` = "English", `TRUE` = "Non-English")\n'
    '    ) +\n'
    '    labs(\n'
    '      title    = "8H. Customer confusion by language x policy area",\n'
    '      subtitle = "Non-English customers: higher confusion rate on which policy areas?",\n'
    '      x = NULL, y = "% customers confused"\n'
    '    ) +\n'
    '    theme_effort() +\n'
    '    coord_flip()\n'
    '  ggsave("chart_p8_language_policy.png", p_8h, width = 10, height = 6,\n'
    '         dpi = 150, bg = WHITE)\n'
    '  cat("  Saved: chart_p8_language_policy.png\\n")\n'
    '} else {\n'
    '  cat("  8H: No language column in data -- add language detection to pipeline to enable.\\n")\n'
    '}\n'
    '\n'
    '\n'
    '# ============================================================================ #\n'
    '# PART 9 - CONSOLE MEGA-SUMMARY                                                #\n'
)
assert OLD8 in txt, "PART 9 header anchor not found"
txt = txt.replace(OLD8, NEW8, 1)
changes.append("8. Block 8H added (language x policy understanding, guarded)")

# ── Write output ──────────────────────────────────────────────────────────────
with open(DEST, "w", encoding="utf-8") as f:
    f.write(txt)

print(f"Written: {DEST}")
print(f"Size: {DEST.stat().st_size:,} bytes  ({DEST.stat().st_size // 1024} KB)")
print(f"\nChanges applied ({len(changes)}):")
for c in changes:
    print(f"  {c}")
print(f"\nOriginal size: {SRC.stat().st_size:,} bytes")
print(f"Original unchanged: {SRC.stat().st_size == Path(SRC).stat().st_size}")
