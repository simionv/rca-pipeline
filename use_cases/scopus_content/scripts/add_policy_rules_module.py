"""
add_policy_rules_module.py
One-time (re-runnable) editor for definitions/scopus_content_pipeline_definition_v2.xlsx:

1. Extends the existing `policy_compliance` module's reference text (modules.description)
   and applicable_policy_codes prompt_instruction to cover PA12-PA18, which were already
   present in the taxonomy sheet but not yet reflected in the LLM-facing prose.
2. Adds a new `policy_rules` module: L1 = policy area (PA1-PA18, reusing policy_compliance's
   codes), L2 = curated, support-relevant atomic rules within each area (49 total), curated
   from POLICY_RULE_SOURCES.md down to rules a customer could plausibly raise or an agent
   could plausibly get wrong.

Re-run after editing this script with:
  uv run python scripts/add_policy_rules_module.py
then rebuild with:
  uv run python build_pipeline.py build --input definitions/scopus_content_pipeline_definition_v2.xlsx --force policy_compliance --force policy_rules
"""
from __future__ import annotations

import openpyxl

XLSX_PATH = "definitions/scopus_content_pipeline_definition_v2.xlsx"

PA12_18_REFERENCE = """
PA12 — PATENT INDEXING AND COVERAGE
Scopus indexes 49.2M+ patent records from five offices: WIPO, EPO, USPTO, JPO, UK IPO. Patents are a distinct content vertical, searchable separately from journal literature. Violation: agent misstates which offices are covered; agent gives wrong guidance on patent search availability. Source: Content Coverage Guide S2.3.

PA13 — AUTHOR IDENTITY AND PROFILE MANAGEMENT
Scopus assigns a unique Author Identifier using algorithmic matching; 17.6M+ profiles; ORCID synced monthly. Profile corrections via Author Feedback Wizard within 5 working days. Violation: agent misstates correction timeline; agent claims merge/demerge is impossible; agent gives wrong Author Feedback Wizard guidance. Source: Content Coverage Guide S3.3.

PA14 — AFFILIATION PROFILE CURATION
Scopus maintains 94,800+ affiliation profiles using algorithmic processing and a curated organisation database. Authorized representatives can request corrections via Institution Profile Wizard. Violation: agent claims corrections cannot be made; agent directs customer to wrong process; agent misstates the responsible team. Source: Content Coverage Guide S3.4.

PA15 — OPEN ACCESS CLASSIFICATION
Scopus classifies articles via Unpaywall: Gold (fully OA journal), Hybrid Gold (OA in subscription journal), Bronze (free on publisher site without explicit licence), Green (accepted manuscript in repository). Applies at document and journal level. Violation: agent confuses OA categories; agent claims OA status cannot be corrected; agent misstates how classification is determined. Source: Content Coverage Guide S3.1.

PA16 — ERRATA AND RECORD CORRECTIONS
Erratum notices are indexed as a distinct document type and linked bidirectionally to the original article. Bibliographic metadata corrections follow the errata capture workflow. A data correction request is processed only when Scopus content differs from the original publisher PDF/source. If Scopus already matches the publisher-supplied PDF, the correction is rejected: the error is between the author and publisher, not in Scopus metadata. Violation: agent claims corrections cannot be processed; agent misstates the processing timeline; agent fails to explain the bidirectional link between erratum and original. Source: Content Coverage Guide S3.1; CAR Manual S6.

PA17 — CITED REFERENCES COVERAGE AND LINKAGE
Scopus indexes cited references for documents from 1970 onward (expanded from 1996 in 2014); pre-1996 data sourced from 60 major publisher archives. References are linked when the cited source is itself indexed; unlinked references appear as plain text. Violation: agent misstates the cutoff year; agent claims older references should be linked when outside coverage; agent fails to explain why some references are not clickable. Source: Content Coverage Guide S3.2, S4.5.

PA18 — MISSING CONTENT PROCESSING ELIGIBILITY
A missing content report is eligible for investigation only when all six criteria are met: (1) the source journal is selected in Scopus; (2) the journal is actively indexed (including ceased and newly-accepted titles); (3) the article publication date falls within the journal's Scopus coverage period; (4) the article can be found at the publisher's authentic online sourcing URL (print and electronic PDFs excluded); (5) the article was published at least 6 weeks before the support request is raised -- content published more recently will not be processed; (6) the document type is Gen-CAR (a Scopus-covered type -- excludes obituaries, reprints, etc.). AiP records bypass criteria 4-5 and follow the PA10 4-day SLA path. Preprints follow PA9 rules. Violation: agent promises to investigate content published less than 6 weeks ago; agent does not verify authentic sourcing URL before escalating; agent quotes a timeline without first checking journal indexing status. Source: CAR Creation Manual (missing content triage).
""".strip()

APPLICABLE_POLICY_CODES_ENUM_TAIL = (
    ", PA10 (AiP eligibility), PA11 (excluded item types), PA12 (patent indexing), "
    "PA13 (author identity), PA14 (affiliation curation), PA15 (open access classification), "
    "PA16 (errata/corrections), PA17 (cited references), PA18 (missing content eligibility)"
)

# (l1_code, l1_label, l1_description, [(rule_label, rule_description), ...])
RULE_AREAS: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    ("PA1", "Title selection and CSAB evaluation",
     "Rules governing whether a journal title qualifies for Scopus consideration and acceptance.", [
        ("Minimum criteria for title consideration",
         "All journal titles must meet all four criteria to be considered: peer-reviewed content with a publicly available peer-review process description; published regularly with an ISSN registered with the ISSN International Centre; English-language abstracts and titles for international readability; a publicly available publication ethics and malpractice statement."),
        ("CSAB five-category evaluation",
         "Journals meeting minimum criteria are evaluated by CSAB on five categories: journal policy (editorial policy, peer review type, editor/author geographic diversity), content (academic contribution, abstract clarity, scope conformity, readability), journal standing (citedness, editor standing), publishing regularity (no schedule delays), and online availability (full online content, English homepage, homepage quality)."),
        ("Title list update cadence",
         "The Scopus title list and Sources section are updated 2-3 times per year; a newly accepted title is only visible in the list as of the next update after its first content appears."),
        ("Post-acceptance feed setup lag",
         "Once a title is accepted, Elsevier contacts the publisher to set up the content feed; it takes up to a few weeks after that before the title's content starts appearing in Scopus."),
     ]),
    ("PA2", "Re-evaluation and discontinuation",
     "Rules governing when an already-indexed title is flagged, re-evaluated, or discontinued.", [
        ("Three-metric, two-year re-evaluation trigger",
         "A journal is flagged for CSAB re-evaluation if it fails all three benchmarks (self-citation rate, total citation rate, CiteScore) versus subject-area peers for two consecutive years."),
        ("Four re-evaluation triggers",
         "Beyond the metrics rule, a title can also be flagged via formal publication-standard complaints from the research community, the RADAR tool (quarterly automated scan for outlier behaviour), or continuous CSAB curation feedback."),
        ("No retroactive removal",
         "When CSAB decides to discontinue a title's forward coverage, content already indexed in Scopus prior to that decision remains in Scopus permanently -- it is never retroactively removed."),
        ("Five-year re-consideration rule",
         "A discontinued title cannot be reconsidered for re-evaluation until 5 years after the discontinuation decision was made."),
     ]),
    ("PA3", "Document type coverage",
     "Rules governing which document types are covered or excluded.", [
        ("Covered document types",
         "Scopus covers these document types: article, article-in-press, book, chapter, conference paper, data paper, editorial, erratum, letter, note, retracted article, review, short survey."),
        ("Book review exclusion",
         "Book reviews are not covered because they are not primary literature, would be identical in full text to the book's own record (causing confusion), and are rarely cited."),
        ("Conference meeting abstract exclusion",
         "Conference meeting abstracts (as opposed to full conference papers) are not covered because they are not a complete or unique record of research, are generally not peer-reviewed, and are typically written before the underlying research is complete."),
        ("Trade journal minimums",
         "Trade journal items require at minimum one named author and one page (or equivalent length for non-paginated electronic sources) to be captured."),
        ("Roman-alphabet title requirement",
         "A citation is only selected for processing when its title is written in a language using the Roman alphabet (i.e. can be captured with a QWERTY keyboard)."),
     ]),
    ("PA4", "Conference proceedings coverage",
     "Rules governing which conference material is covered.", [
        ("Full-text-only conference coverage",
         "Only conference proceedings that publish full-text papers are covered; proceedings that publish only abstracts (meeting abstracts) are not considered for coverage."),
        ("Conference subject-area focus",
         "Conference proceedings coverage is concentrated in subject areas where conference papers make up a substantial share of published research, primarily engineering, computer science, and some areas of physics."),
     ]),
    ("PA5", "Processing timelines",
     "Rules governing how long standard (non-AiP) content takes to appear in Scopus.", [
        ("Electronic delivery timeline",
         "For electronically delivered content (e-feeds, over 95% of material), fully indexed article data typically appears in Scopus within 2-3 weeks of publication on the publisher's website."),
        ("Paper delivery timeline",
         "For the shrinking share of content still delivered in paper format, processing and indexing takes 4-5 weeks, depending on distribution and delivery from the publisher's warehouse."),
     ]),
    ("PA6", "Coverage period and historical content",
     "Rules governing how far back a title's coverage extends.", [
        ("Selection-year-minus-4 coverage start",
         "For titles selected from 2023 onward, coverage begins from the year of selection minus 4 (e.g. selected in 2023 -> coverage starts from 2019), with exceptions for journals that have prior evaluation history."),
        ("Pre-1996 discontinued titles still searchable",
         "Titles discontinued before 1996 are not shown in the public title list, but their previously indexed content remains searchable in Scopus."),
     ]),
    ("PA7", "Metrics methodology",
     "Rules governing how Scopus and third-party metrics are calculated.", [
        ("CiteScore calculation",
         "CiteScore is calculated as citations in year X to documents published in years X-3 through X, divided by the number of documents published in years X-3 through X, and is recalculated annually."),
        ("SJR/SNIP are third-party metrics",
         "SJR and SNIP are calculated by third parties (SCImago and CWTS respectively) -- Scopus does not control or recalculate them."),
     ]),
    ("PA8", "Book and book series selection",
     "Rules governing how books and book series are selected.", [
        ("Publisher-based book selection",
         "Book selection evaluates a publisher's complete books list, not individual titles; once a publisher is accepted, in-scope books from that publisher are indexed. Individual book suggestions outside the publisher review process are not accepted."),
        ("Dual book/chapter indexing",
         "Books are indexed at both the book level and the individual chapter level."),
     ]),
    ("PA9", "Preprint server coverage",
     "Rules governing which preprint servers are indexed.", [
        ("Seven supported preprint servers",
         "Only these preprint servers are indexed: arXiv and ChemRxiv (Physical Sciences), bioRxiv and MedRxiv (Biomedical Sciences), SSRN (Social Sciences), TechRxiv (Engineering/CS), and Research Square (Multidisciplinary)."),
        ("Preprints don't affect metrics",
         "Preprints do not affect a researcher's or journal's existing publication or citation metrics in Scopus."),
     ]),
    ("PA10", "Article-in-Press (AiP) eligibility and processing",
     "Rules specific to Article-in-Press items, distinct from standard processing (PA5).", [
        ("Mandatory DOI for AiP",
         "A DOI is mandatory for all Article-in-Press (AiP) items; this is not optional."),
        ("Four-day AiP SLA",
         "AiP items are made available in Scopus within 4 days of the publisher's FTP delivery to Scopus -- distinct from and faster than the standard 2-3 week electronic-delivery timeline (PA5)."),
        ("No volume/issue/page required for AiP",
         "AiP records are not required to carry volume, issue, or page data."),
        ("No grant info for AiP",
         "Grant/funding information is not captured for AiP items."),
     ]),
    ("PA11", "Excluded item types",
     "Rules on item types never indexed regardless of source (CAR Manual S1 list).", [
        ("Non-primary-literature exclusions",
         "Book reviews, personal reports, obituaries (including 'In Memoriam'), indexes, and addendums are not indexed -- they are not primary research literature."),
        ("Promotional/notice content exclusions",
         "Advertisements, society news, notices of future conferences/events, award winner notifications, Instructions to Authors, and 'In this issue'/table-of-contents items are not indexed."),
        ("Duplicate/derivative content exclusions",
         "Reprints of articles published elsewhere, and product/video/audio reviews, are not indexed."),
     ]),
    ("PA12", "Patent indexing and coverage",
     "Rules governing Scopus's patent content vertical.", [
        ("Five-office patent coverage",
         "Scopus indexes 49.2M+ patent records sourced from exactly five patent offices: WIPO, EPO, USPTO, JPO, and the UK IPO. Patents are a distinct content vertical from journal literature."),
     ]),
    ("PA13", "Author identity and profile management",
     "Rules governing Scopus Author Identifier assignment and correction.", [
        ("Author Feedback Wizard, 5 working days",
         "Authors can request corrections to their Scopus Author profile via the Author Feedback Wizard; changes are implemented within 5 working days."),
        ("Monthly ORCID sync",
         "Once an author connects their Scopus Author Identifier to ORCID, the two systems sync data on a monthly basis -- not in real time."),
     ]),
    ("PA14", "Affiliation profile curation",
     "Rules governing institution/affiliation profile correction.", [
        ("Institution Profile Wizard corrections",
         "Corrections to an institution's affiliation profile can be requested via the Institution Profile Wizard, but only by an authorized representative of that institution."),
     ]),
    ("PA15", "Open Access classification",
     "Rules governing how OA status is determined and classified.", [
        ("DOAJ/ROAD journal-level OA registration",
         "A journal is registered as Open Access in Scopus only if it is listed as Gold or Subsidized OA on the Directory of Open Access Journals (DOAJ) or the Directory of Open Access Scholarly Resources (ROAD)."),
        ("Four-way document OA classification",
         "Individual documents are classified as Gold (published version, CC-licensed, OA-only journal), Hybrid Gold (published version, CC-licensed, subscription journal offering an OA option), Bronze (free to read but no CC license, unclear license, or publisher-specific license), or Green (accepted-manuscript or published version available in a repository)."),
        ("Automated Unpaywall-sourced classification",
         "Open Access status is determined automatically by Unpaywall, not manually assigned by Scopus staff -- it updates if Unpaywall's underlying data changes, and cannot be manually toggled on request."),
     ]),
    ("PA16", "Errata and record corrections",
     "Rules governing erratum linkage and data-correction eligibility.", [
        ("Bidirectional erratum linkage",
         "An erratum or retraction notice is indexed as its own document type and is linked bidirectionally to the original article it corrects."),
        ("Correction only if Scopus differs from publisher PDF",
         "A data correction request is processed only when the Scopus record differs from the original publisher-supplied PDF/source. If Scopus already matches the publisher's PDF, the correction request is rejected -- the discrepancy is between the author and publisher, not an error in Scopus's metadata."),
     ]),
    ("PA17", "Cited references coverage and linkage",
     "Rules governing how far back references are indexed and when they are linked.", [
        ("1970 cutoff, pre-1996 archive backfill",
         "Scopus indexes cited references for documents back to 1970 (expanded from 1996 in a 2014 project); references for documents published before 1996 were backfilled from the archives of 60 major publishers."),
        ("References linked only if the cited source is itself indexed",
         "A cited reference is only clickable/linked in Scopus if the source it cites is itself indexed in Scopus; otherwise it appears as plain, unlinked text."),
     ]),
    ("PA18", "Missing content processing eligibility",
     "The six eligibility criteria a missing-content report must meet before investigation.", [
        ("Journal must be selected",
         "A missing content report is only eligible for investigation if the source journal is selected in Scopus."),
        ("Journal must be actively indexed",
         "The journal must be actively indexed, including titles that are ceased or newly accepted -- a journal that was never indexed, or was rejected, does not qualify."),
        ("Publication date within coverage period",
         "The article's publication date must fall within the journal's Scopus coverage period (see PA6)."),
        ("Authentic online sourcing URL required",
         "The article must be found at the publisher's authentic online sourcing URL; print and electronic PDF copies supplied directly by the customer are excluded as a source for verification."),
        ("Six-week publication maturity",
         "The article must have been published at least 6 weeks before the support request is raised; content published more recently will not be processed as missing, since it may still be in the normal processing pipeline (see PA5)."),
        ("Gen-CAR document type required",
         "The missing item must be a Scopus-covered ('Gen-CAR') document type; items in the PA11 exclusion list (obituaries, reprints, etc.) do not qualify as missing content. AiP items bypass criteria 4 and 5 and instead follow the PA10 4-day SLA path; preprints follow PA9 rules."),
     ]),
]


def main() -> None:
    wb = openpyxl.load_workbook(XLSX_PATH)

    # --- 1. Extend policy_compliance's reference text to cover PA12-18 ---
    ws_mod = wb["modules"]
    header = [c.value for c in ws_mod[1]]
    col = {h: i + 1 for i, h in enumerate(header)}
    for row in ws_mod.iter_rows(min_row=2):
        if row[col["module_name"] - 1].value == "policy_compliance":
            desc_cell = row[col["description"] - 1]
            desc = desc_cell.value or ""
            if "PA12" not in desc:
                desc = desc.replace(
                    "(PA10 AiP, PA11 excluded item types).",
                    "(PA10 AiP, PA11 excluded item types, PA16 errata, PA18 missing-content eligibility);\n"
                    "and further Content Coverage Guide areas PA12-PA15 and PA17.",
                )
                desc = desc.rstrip() + "\n\n" + PA12_18_REFERENCE
                desc_cell.value = desc
                print("Updated policy_compliance modules.description with PA12-18 reference text")
            break

    # --- 2. Extend applicable_policy_codes prompt_instruction to enumerate PA10-18 ---
    ws_fld = wb["fields"]
    fheader = [c.value for c in ws_fld[1]]
    fcol = {h: i + 1 for i, h in enumerate(fheader)}
    for row in ws_fld.iter_rows(min_row=2):
        if (row[fcol["module_name"] - 1].value == "policy_compliance"
                and row[fcol["field_name"] - 1].value == "applicable_policy_codes"):
            pi_cell = row[fcol["prompt_instruction"] - 1]
            pi = pi_cell.value or ""
            if "PA18" not in pi:
                pi = pi.replace("PA9 (preprints).", "PA9 (preprints)" + APPLICABLE_POLICY_CODES_ENUM_TAIL + ".")
                pi_cell.value = pi
                print("Updated applicable_policy_codes prompt_instruction to enumerate PA10-PA18")
            break

    # --- 3. Add the policy_rules module row (skip if already present) ---
    if any(row[col["module_name"] - 1].value == "policy_rules" for row in ws_mod.iter_rows(min_row=2)):
        print("policy_rules module row already exists — skipping steps 3-6 "
              "(delete its modules/fields/taxonomy rows first to re-add from scratch)")
        wb.save(XLSX_PATH)
        return
    ws_mod.append([
        "policy_rules",       # module_name
        "PA",                 # taxonomy_prefix
        "policy_rules.json",  # taxonomy_file
        "policy_rules",       # reorder_group
        5,                    # reorder_order
        True,                 # enabled
        "You are an expert classifier for Elsevier support tickets. Your task: identify which "
        "SPECIFIC Scopus content policy rules (not just broad policy areas) applied to this "
        "ticket, and whether the agent's handling complied with each one individually. Each leaf "
        "code in the taxonomy below (e.g. PA5.1, PA10.2) is one atomic, checkable rule drawn from "
        "the Scopus Content Coverage Guide and CAR Creation Manual. A ticket may touch multiple "
        "rules across one or more policy areas, or none at all. Use the taxonomy below to make "
        "your assessment.",   # description (-> _BEFORE)
        "Curated support-relevant subset of POLICY_RULE_SOURCES.md (49 of 100+ extracted rules); "
        "companion to policy_compliance, reuses its PA1-PA18 area codes as L1.",  # notes
        "",                   # discovery_mode
        "",                   # extract_prompt
    ])

    # --- 4. Add the matched_rules field row ---
    ws_fld.append([
        "policy_rules",                                    # module_name
        "matched_rules",                                   # field_name
        "list",                                             # field_type
        "Specific policy rules relevant to this ticket, each with its own compliance verdict",  # description
        "Review the ticket against the numbered policy rules in the taxonomy below (each leaf "
        "code like PA5.1 or PA10.2 is one specific, atomic rule). For every rule that is "
        "genuinely relevant to this ticket's topic -- i.e. the rule's subject matter was raised, "
        "or should have governed the agent's response -- return one object with: 'code' (the "
        "exact leaf code), 'verdict' (one of: compliant, non_compliant, partial, not_applicable), "
        "and 'evidence' (a single verbatim quote copied EXACTLY, character-for-character, from the "
        "customer/agent conversation text -- NEVER the rule description itself, a paraphrase, or a "
        "summary. If you cannot find such an exact quote in the conversation, return an empty string "
        "for evidence -- do not describe the rule instead). compliant = the agent's handling matched "
        "this specific rule. non_compliant = the agent's handling directly contradicted or "
        "ignored this specific rule. partial = broadly correct but missed or misstated a detail "
        "of this specific rule. not_applicable = the rule's topic was raised but this particular "
        "rule doesn't govern the outcome (rare -- prefer omitting the rule entirely over tagging "
        "it not_applicable). If no rules in the taxonomy are relevant to this ticket at all, "
        "return an empty list []. Only return rules that are genuinely relevant -- do not return every "
        "rule in the taxonomy for every ticket. Do not tag a rule just because the ticket's general "
        "topic is nearby (e.g. any metadata-correction ticket is NOT automatically every PA18 "
        "criterion) -- only tag a rule if the conversation specifically discusses, triggers, or should "
        "have triggered that exact rule. Most tickets will match 0-2 rules; a ticket matching many "
        "rules from the same area is a red flag -- double-check each one individually rather than "
        "tagging the whole area at once. When in doubt, leave the rule out. Do NOT reuse the identical "
        "evidence quote across multiple different rule codes -- if the same quote would 'support' every "
        "sub-criterion in an area, that is a sign you should tag only the ONE rule that quote most "
        "specifically and distinctly supports, not all of them. Before tagging any PA18 (missing content) "
        "criterion, confirm the ticket is genuinely about content that has never been indexed and is "
        "reported missing -- a request to correct or fix data on content that IS already indexed is PA16 "
        "(errata/corrections), not PA18, even if the customer also mentions the item is 'missing' from "
        "their profile view.",     # prompt_instruction
        True,                                                # in_output
        True,                                                # explode_list
        False,                                               # validate_enum (nested, not top-level -- see notes)
        "List of {code, verdict, evidence} objects, not a flat code list. "
        "explode_keys=code,verdict,evidence drives exploding into matched_rules_code_N/_verdict_N/_evidence_N "
        "(key-then-slot naming so *_code_N triggers automatic label derivation). "
        "verdict is validated by the LLM prompt only (no generated top-level enum validator, since it is "
        "nested inside list items).",  # notes
    ])
    # explode_keys column: appended separately below once we know if it already exists.

    # --- 5. Add explode_keys column if not already present, and set it for matched_rules ---
    if "explode_keys" not in fheader:
        new_col_idx = len(fheader) + 1
        ws_fld.cell(row=1, column=new_col_idx, value="explode_keys")
        fheader.append("explode_keys")
        fcol["explode_keys"] = new_col_idx
    for row in ws_fld.iter_rows(min_row=2):
        if (row[fcol["module_name"] - 1].value == "policy_rules"
                and row[fcol["field_name"] - 1].value == "matched_rules"):
            row[fcol["explode_keys"] - 1].value = "code,verdict,evidence"
            break

    # --- 6. Add the policy_rules taxonomy rows (18 L1 areas x their curated rules) ---
    ws_tax = wb["taxonomy"]
    n_l1 = 0
    n_l2 = 0
    for area_code, area_label, area_desc, rules in RULE_AREAS:
        ws_tax.append(["policy_rules", "L1", area_label, area_desc, None, area_code])
        n_l1 += 1
        for rule_label, rule_desc in rules:
            ws_tax.append(["policy_rules", "L2", rule_label, rule_desc, None, None])
            n_l2 += 1

    wb.save(XLSX_PATH)
    print(f"Saved. Added policy_rules taxonomy: {n_l1} L1 areas, {n_l2} L2 rules.")


if __name__ == "__main__":
    main()
