"""
Apply the SME review of 2026-06-12 to the LeapSpace gold set.

Evidence check showed the reviewed quotes live in data/leapspace_collapsed.csv
(the bulk 1,326-ticket dataset), NOT in the existing gold set — the SME reviewed
bulk-run predictions. So each review row is:
  1. Quote-matched against the BULK conversations (primary, exact-1 match)
  2. If the matched conversation already exists in the gold set → update in place
  3. Otherwise → appended to the gold set as a new gold ticket
     (Ticket Number = bulk Incident_ID)

Rows whose quote can't be located (SME paraphrases) are reported for manual ID —
never guessed.

Outputs:
  data/leapspace_gold_review_2026-06-12.csv        — the review rows as a file
  data/leapspace_gold_set_backup_2026-06-12.xlsx   — pre-update backup
  data/leapspace_gold_set.xlsx                     — updated in place
  data/gold_review_match_report.csv                — audit: matched/ambiguous/unmatched

Usage (from project root):
    python scripts/apply_gold_review.py
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent.parent
GOLD_SET    = BASE / "data/leapspace_gold_set.xlsx"
BULK_CSV    = BASE / "data/leapspace_collapsed.csv"
REVIEW_CSV  = BASE / "data/leapspace_gold_review_2026-06-12.csv"
BACKUP      = BASE / "data/leapspace_gold_set_backup_2026-06-12.xlsx"
REPORT_CSV  = BASE / "data/gold_review_match_report.csv"

# Normalise SME label variants → canonical labels
LABEL_FIXES = {
    "Institutional user access issue": "Institutional user cannot access",
}

# (old_cr, old_rc, new_cr, new_rc, new_description, comments)
REVIEW_ROWS = [
    ("Trial inquiry", "Service request for trial",
     "Trial inquiry", "Service request for trial",
     "The user requested support to set up or activate free trial",
     'Quote"We have several events coming up where we will be demoing our solutions. Would it be possible to get bulk/trial keys for"'),

    ("Institutional access issues", "Guidance on individual subscription / free trial access",
     "Institutional user cannot access", "Change-org feature error",
     "Institutional user who has multiple organisational accounts encounters an access issue",
     'Quote :"LS Product Team identified the issue with the change organization and multiple user associations"'),

    ("Institutional access issues", "LeapSpace trial had not been enabled",
     "Trial testing", "Access methods flows clarification",
     "Elsevier employee checks access flows for an institution",
     "Quote: today the trial for LeapSpace started and we need to make sure the access based on the IP and personal credentials runs smoothly"),

    ("User not able to access", "Session data conflict",
     "Institutional user cannot access", "Entitlement provisioning error",
     "The user is unable to access LeapSpace because their institutional entitlement was not correctly provisioned",
     "Quote: Agent Notes: LeapSpace is entitled at the account level for Toyota Industries Corporation (ECR-441657)"),

    ("User not able to access", "Session data conflict",
     "Institutional user access issue", "Entitlement provisioning error",
     "The user is unable to access LeapSpace because their institutional entitlement was not correctly provisioned",
     "Quote: Unable to access LeapSpace via institution. Entitlement is enabled but user cannot log in. "
     "Troubleshooting done — multiple sessions including a call, still not working. Raised Jira RSAI-1264. "
     "Product confirmed this is a known issue. Interim fix: entitlement created at customer level. "
     "Customer confirmed access is now working."),

    ("User not able to access", "User not entitled",
     "NA", "NA", "", ""),

    ("User not able to access", "Entitlement provisioning error",
     "Institutional user cannot access", "Access method unavailable",
     "Institutional user cannot access LeapSpace because of access method unavailability",
     'Quote"Upon reviewing the issue, our Product Team has confirmed that accessing LeapSpace via proxy is currently unavailable"'),

    ("Other not access related", "LeapSpace result inconsistency",
     "Other not access related", "unable to access full-text articles",
     "The customer reported an issue with accessing full-text articles due to internal IT security controls",
     "Quote: a key manager at ASE reported that they are unable to access full-text articles via the provided "
     "links in LeapSpace. This appears to be due to their internal IT security controls"),

    ("Subscription cancellation and (or) refund", "Cancellation and or refund service request",
     "Billing", "Payment issues",
     "The user is encountering a payment error during the subscription initiation/renewal",
     "Quote: when I reach the step where I should select the payment information, there is no option/menu to "
     "choose a payment method/card; The rejection appears to have come from the Adyen payment gateway. The most "
     "recent monthly subscription #S-3815 payment attempt also failed due to rejection by the payment portal"),

    ("Internal staff access", "Not enough info",
     "Internal staff access", "Change-org feature error",
     "Elsevier employee cannot access LeapSpace because “Change organization” feature not working as intended",
     "Quote: the “Change organization” feature is currently not working as intended. Almost no one in the "
     "Japan CSM team is able to use LeapSpace"),

    ("Institutional access issues", "Entitlement provisioning error",
     "Institutional user cannot access", "Entitlement provisioning error",
     "The user is unable to access LeapSpace because their institutional entitlement was not correctly configured",
     "Quote: we are having logging issues with a trial we are running in the Netherlands. Issue is resolved "
     "after E-Delivery Team moved the entilement from department level to account level"),

    ("User not able to access", "User not entitled",
     "User not able to access", "Not enough info",
     "Although the user has an active subscription verified their email cannot be found in CHIEF",
     "Quote: They did quote the wrong email address though. I have a science direct AI subscription It seems "
     "that I can login but I cnnont accesss the page anymore."),

    ("Internal staff access", "Not enough info",
     "General info not access related", "Questions about LeapSpace features",
     "The user is experiencing issues with the character limit in LeapSpace, believing it to be a word limit instead",
     "Quote: you first asked about the 500 words you are trying to enter in LeapSpace. We advised that "
     "LeapSpace's limit is 500 character and not words"),

    ("Institutional access issues", "LeapSpace trial had not been enabled",
     "Billing", "Payment issues",
     "The user is encountering a payment error during the subscription initiation/renewal",
     "Quote: when I reach the step where I should select the payment information, there is no option/menu to "
     "choose a payment method/card; The rejection appears to have come from the Adyen payment gateway. The most "
     "recent monthly subscription #S-3815 payment attempt also failed due to rejection by the payment portal"),

    ("General info not access related", "Questions about LeapSpace features",
     "General info not access related", "Questions about LeapSpace features",
     "The customer is providing feedback about the new LeapSpace interface and requesting a feature that "
     "resembles the previous system.",
     "Quote :I find the new LeapSpace interface significantly more complex and cluttered compared to the "
     "previous layout. The original interface was much more aligned with my research needs due to its "
     "simplicity and ease of use. Since I am paying for this service individually, I would like to formally "
     "request that Elsevier considers providing a 'Legacy View' or a 'Classic Mode' for users who prefer the "
     "previous system’s functionality"),

    ("Institutional access issues", "Elsevier ID+ SSO access denied error",
     "Institutional user cannot access", "Session data conflict",
     "The user is experiencing an access denied error when trying to access LeapSpace, although does not "
     "return to the conversation after troubleshooting steps were provided",
     "Quote: Could you please try clearing your browser’s cache and cookies to > remove any previous "
     "sessions? Then, try accessing LeapSpace again"),

    ("Institutional access issues", "Not enough info",
     "Institutional user cannot access", "User not entitled",
     "User is unable to access LeapSpace bacause they were not linked to institution",
     "Quote: I’ve reviewed the user’s profile and can confirm that the issue is due to the account not "
     "being associated with the institution Maggiano, DiGirolamo & Lizzi P.C. Since this is an institutional "
     "LeapSpace subscription, users must be explicitly linked to the institution for access to work properly"),

    ("Institutional access issues", "LeapSpace trial had not been enabled",
     "User not able to access", "Session data conflict",
     "User is unable to access LeapSpace after renewing individual subscription,  as they were logging in via "
     "his institution's SSO, which created a conflict",
     "Quote: I guided the user to access LeapSpace > user needed to access SD via UTP SSO then opened a new "
     "tab > copy pasted https://www.sciencedirect.com/leapspace > access worked"),

    ("Billing", "Payment issues",
     "User not able to access", "Entitlement provisioning error",
     "The user cannot access because subscription did not activate properly in the system, payment was "
     "processed but CHIEF was not updated to reflect an active LeapSpace membership",
     "Quote:No new active subscription for LeapSpace was found under the customer’s account. The problem "
     "seems to be that the subscription didn’t activate properly. Even though the payment went through, "
     "the system (CHIEF) didn’t update to show an active LeapSpace"),

    ("Other not access related", "LeapSpace result inconsistency",
     "Other not access related", "Content format",
     "A user reports an inconsistency in reference numbers when exporting data from LeapSpace to Word, and "
     "data is auto-adapting to Word format",
     "Quote:I understand that our user from Beiersdorf is getting incorrect reference numbers from LeapSpace. "
     "It seems that the numbering is auto-adapted by Word when copying, in Leapspace itself the numbering is correct"),

    ("Institutional access issues", "Not enough info",
     "Institutional user cannot access", "Incorrect organisation chosen",
     "Trial users unable to access LeapSpace",
     'Quote:Users should select "LeapSpace-External Agencies" because this is where they get their LeapSpace '
     "access. They need to change this by clicking the house icon inside ScienceDirect first. Once done, open "
     "a new tab then access LeapSpace."),

    ("User not able to access", "User not entitled",
     "Subscription renewal", "Billing",
     "User cannot renew subscription and his payment is getting declined",
     "Quote:here are the specific refusal reasons for the transaction: It appears that customer tried multiple "
     "times with different Visa and Mastercard. Visa: The issuing bank will not allow this transaction"),

    ("User not able to access", "Entitlement provisioning error",
     "Billing", "Payment issues",
     "The user is encountering a payment error during the subscription initiation/renewal",
     "Quote: when I reach the step where I should select the payment information, there is no option/menu to "
     "choose a payment method/card; The rejection appears to have come from the Adyen payment gateway. The most "
     "recent monthly subscription #S-3815 payment attempt also failed due to rejection by the payment portal"),

    ("Subscription cancellation and (or) refund", "Forgot to cancel",
     "User not able to access", "Not enough info",
     "The customer is reporting a 403 access error when trying to access their LeapSpace trial and is seeking "
     "verification of their account entitlement",
     'Quote: I receive a 403 / “No access” message stating that my account is not subscribed'),

    ("General info not access related", "Difference between LeapSpace and Scopus AI",
     "General info not access related", "Difference between LeapSpace and Scopus AI",
     "The customer asked whether Ask ScienceDirect AI is still available as a standalone tool, and provided "
     "detailed feedback comparing it unfavourably to LeapSpace",
     "Quote: Is this tool still available as a separate and standalone feature as it was previously, or has it "
     "now been fully integrated into LeapSpace and is no longer accessible independently?"),

    ("Billing", "Payment method update",
     "Billing", "Payment method update",
     "The customer is unable to renew their subscription due to conflicting messages about their existing "
     "subscription status.",
     "Quote: The shopper should contact their issuing bank for clarification"),

    ("User not able to access", "Session data conflict",
     "Institutional user cannot access", "Not enough info",
     "The user is unable to access LeapSpace via SSO authentication despite following troubleshooting steps.",
     "Quote: Our user reported that she is unable to access LeapSpace via SSO authentication"),

    ("Subscription cancellation and (or) refund", "Cancellation and or refund service request",
     "Subscription cancellation and (or) refund", "Cancellation and or refund service request",
     "The user was charged for a subscription after a trial period and is requesting a refund for the charge.",
     "Quote: I do not wish to continue the subscription and would like to request a refund for this charge"),

    ("User not able to access", "User not entitled",
     "User not able to access", "Not enough info",
     "The user is unable to access LeapSpace after payment — requesting compensation for downtime",
     "Quote: I have received the access to LeapSpace now. Please compensate for the downtime"),

    ("Subscription request (incl. resub)", "Subscription service request",
     "Subscription request (incl. resub)", "Subscription service request",
     "Request to switch from monthly to annual LeapSpace subscription",
     "Quote: How can I change from monthly to annual?"),
]


def norm(s: str) -> str:
    """Lowercase, strip all punctuation/unicode to spaces, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(s).lower())).strip()


def quote_fragments(comments: str) -> list[str]:
    """Extract normalised quote fragments from a comments cell, longest first.

    Splits on ; > and sentence boundaries — SME quotes often stitch verbatim
    sentences together with their own paraphrase, so each sentence is tried
    separately.
    """
    text = re.sub(r"^\s*quote\s*[:\"“]?\s*", "", comments.strip(), flags=re.I)
    parts = re.split(r"[;>.?!]", text)
    frags = {norm(p) for p in parts + [text] if norm(p)}
    return sorted((f for f in frags if len(f) >= 25), key=len, reverse=True)


def main() -> None:
    review = pd.DataFrame(
        REVIEW_ROWS,
        columns=["old_cr", "old_rc", "new_cr", "new_rc", "new_description", "comments"],
    )
    review.to_csv(REVIEW_CSV, index=False, encoding="utf-8-sig")
    print(f"Review saved: {REVIEW_CSV.name}  ({len(review)} rows)")

    gold = pd.read_excel(GOLD_SET)
    gold["Ticket Number"] = gold["Ticket Number"].astype(str).str.strip()
    bulk = pd.read_csv(BULK_CSV)

    # Normalised conversations: bulk (primary match target) and gold (dedupe)
    bulk_rows: list[tuple[str, str, str]] = []  # (incident_id, norm_text, raw_text)
    for _, r in bulk.iterrows():
        raw = str(r["Conversation"])
        bulk_rows.append((str(r["Incident_ID"]), norm(raw), raw))
    gold_norm = {str(r["Ticket Number"]): norm(r["Conversation"]) for _, r in gold.iterrows()}

    report_rows: list[dict] = []
    assigned: dict[str, int] = {}  # incident_id -> review row idx (first claimant)
    updates: dict[str, tuple[str, str, str]] = {}          # gold uid -> correction
    appends: list[dict] = []                               # new gold rows

    for idx, row in review.iterrows():
        new_cr = LABEL_FIXES.get(row["new_cr"].strip(), row["new_cr"].strip())
        new_rc = row["new_rc"].strip()
        desc   = row["new_description"].strip()
        status, uid, how = "", "", ""

        if new_cr.upper() == "NA":
            status = "skipped (NA)"
        else:
            # Quote-substring match against bulk conversations
            candidates: list[tuple[str, str, str]] = []
            for frag in quote_fragments(row["comments"]):
                candidates = [(i, t, raw) for i, t, raw in bulk_rows if frag in t]
                if candidates:
                    how = f"quote ({len(frag)} chars)"
                    break

            # Drop tickets already claimed by an earlier review row
            # (the Adyen quote appears in multiple rows AND multiple tickets)
            free = [c for c in candidates if c[0] not in assigned]

            if len(free) == 1:
                inc_id, ntext, raw = free[0]
                assigned[inc_id] = idx
                # Dedupe: is this conversation already a gold ticket?
                gold_uid = next((g for g, gt in gold_norm.items() if gt == ntext), None)
                if gold_uid:
                    updates[gold_uid] = (new_cr, new_rc, desc)
                    uid, status = gold_uid, "matched -> updated existing gold ticket"
                else:
                    appends.append({
                        "Ticket Number": inc_id,
                        "Conversation":  raw,
                        "Contact Reason": new_cr,
                        "Root Cause":     new_rc,
                        "Explanations":   desc,
                    })
                    uid, status = inc_id, "matched -> added as new gold ticket"
            elif len(candidates) >= 1 and not free:
                prev = assigned.get(candidates[0][0])
                status = f"duplicate quote (ticket(s) already claimed by row {prev})"
            elif len(free) > 1:
                # Multiple unclaimed tickets share the quote and corrections are
                # identical across the duplicate rows -> take the first.
                inc_id, ntext, raw = free[0]
                assigned[inc_id] = idx
                appends.append({
                    "Ticket Number": inc_id,
                    "Conversation":  raw,
                    "Contact Reason": new_cr,
                    "Root Cause":     new_rc,
                    "Explanations":   desc,
                })
                uid = inc_id
                status = f"matched (1 of {len(free)} candidates -> added)"
            else:
                status = "UNMATCHED (quote not found in bulk — SME paraphrase?)"

        report_rows.append({
            "row": idx, "old_cr": row["old_cr"], "old_rc": row["old_rc"],
            "new_cr": new_cr, "new_rc": new_rc,
            "matched_uid": uid, "method": how, "status": status,
        })

    # ── Apply: backup, update in place, append new rows ──────────────────────
    shutil.copy2(GOLD_SET, BACKUP)
    for g_uid, (cr, rc, desc) in updates.items():
        mask = gold["Ticket Number"] == g_uid
        gold.loc[mask, "Contact Reason"] = cr
        gold.loc[mask, "Root Cause"] = rc
        if desc:
            gold.loc[mask, "Explanations"] = desc
    if appends:
        gold = pd.concat([gold, pd.DataFrame(appends)], ignore_index=True)
    gold.to_excel(GOLD_SET, index=False)

    # ── Report ────────────────────────────────────────────────────────────────
    rep = pd.DataFrame(report_rows)
    rep.to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")

    print(f"\nBackup:  {BACKUP.name}")
    print(f"Updated: {GOLD_SET.name}  — {len(updates)} updated, "
          f"{len(appends)} added, now {len(gold)} tickets")
    print(f"Report:  {REPORT_CSV.name}\n")

    counts = rep["status"].str.split(" ").str[0].value_counts()
    print("Match summary:", dict(counts))
    problems = rep[rep["status"].str.contains("UNMATCHED")]
    if not problems.empty:
        print("\nRows needing manual ticket IDs:")
        for _, r in problems.iterrows():
            print(f"  row {r['row']:2d}  old: {r['old_cr']} / {r['old_rc']}")
            print(f"          new: {r['new_cr']} / {r['new_rc']}")

    # New CR->RC pairs now present in the gold set (for the taxonomy update)
    print("\nDistinct CR -> RC pairs in updated gold set:")
    pairs = gold.groupby(["Contact Reason", "Root Cause"]).size().reset_index(name="n")
    for _, p in pairs.iterrows():
        print(f"  {p['Contact Reason']}  ->  {p['Root Cause']}   ({p['n']})")


if __name__ == "__main__":
    main()
