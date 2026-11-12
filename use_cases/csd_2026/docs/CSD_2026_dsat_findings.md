# Why customers score us badly when we say no

Deep dive on dissatisfied Scopus CSD tickets, 2026 (Jan–Jul).
Workbook: `runs/output/csd_2026_dsat_deepdive.xlsx` — 16 sheets.

**Start with `read_these_30`** (the sample), then `side_by_side` (each one against a matched
satisfied ticket). Everything else is evidence behind the six answers below.

---

## The short version

**The process is not the problem. The explanation is.**

On 88% of dissatisfied tickets an independent read of the transcript concluded that nothing about
the handling would have reduced the customer's effort — the exchange was already direct. But on
**45% the refusal was delivered with no reason given**, and on a further 21% with no next step.
Only 31% of replies had nothing wrong with them.

Among the 110 customers who chose **"Policy"** as their reason for dissatisfaction — the largest
group, the ones ostensibly just angry that we said no — **61 (55%) were never told why**.

That reframes the problem. These are not people who are unhappy because the answer was no. They
are people who were told no without being told why.

---

## 1 · Are tickets held open until resolved, or closed with things pending?

**Mostly closed, and closed decisively — but the data cannot fully settle this, and that is itself
worth knowing.**

The documented process is unambiguous. The CheatSheet tab `OSVC Best Practices - Status`
prescribes a parent/child model: the parent incident sits `In progress` while a Task goes to 2LS
with a private note, and only after **"Confirmed Completed — YES"** does the flow say respond to
the customer and Solve.

What the extract can show:

| | |
|---|---:|
| `status_desc` | Solved 57,815 · Closed 61 |
| Rows with a close timestamp | 100% |
| Tickets ending in a 2LS group | **600** (1.0%) |
| …of those, with a CSAT response | **1** |
| Tickets LLM-flagged "Escalation required" | 5,890 |
| Tickets flagged "Redirected to another party" | 6,167 |
| Tickets closed with **no agent response at all** | 1,337 |
| Median days to close, 1LS vs 2LS | 2.3 vs 11.7 |

**The transcript read says 10%.** Of 272 reviewed dissatisfied tickets, **26 ended with something
still outstanding** — an awaited escalation, a promised follow-up, an unanswered question. The
other 90% were concluded, by a refusal.

Two caveats that must travel with this. The export is **terminal-state only**, and the two places
pending work would appear are both absent: `THREAD_ENTRY_TYPE` has only Staff/Customer entries
with no note type, and `INCIDENT_TYPE` is constant, so child Tasks are not exported. And properly
escalated work carries an **"Out" action code** (`Sent to Supplier-Missing article`, 10,779 in
2026) which is **not in this corpus at all**. So the gap between 5,890 escalation-flagged and 600
2LS-ending tickets most likely reflects customers being told to pursue it themselves rather than
internal escalation going unrecorded — see question 5.

## 2 · The OSvC taxonomy

Three sheets: `tax_contact_reasons`, `tax_resolution_codes`, `tax_other_fields`.

- **Contact reason** — 30 level-1 values, 81 level-2, as a hierarchy with counts. Heavily
  concentrated: `Add Missing Document / Missing Article on Scopus` alone is 41,733 of 57,876 (72%).
  The tree is not strict — `Other`, `Missing Article(s)` and `Status` each appear under more than
  one parent, so the (lvl1, lvl2) pair is the only safe key.
- **Resolution codes** — all 15 live codes, with 2025/2026 volumes and, usefully, the workbook's own
  policy-type flags: **7 are coverage-policy rejections, 6 capturing-guideline, 4 process**. That
  is the cleanest available way to say *what kind* of no a ticket received.
- **Customer role / type / product, channel, agent group, status** — full value counts.

Three cautions. **All 15 codes here begin `Invalid-`; the reference lists 74 "Out" action codes
that are absent**, so this data covers roughly half the outcome space and contains no actioned
ticket to compare against. The sanctioned code list is **out of date** — `Invalid-Not within scope`
and `Invalid- Out of coverage` are live but not on it. And the discriminating power is thin:
`IS_VALUE_ADD` is constant, `status_desc` is 99.9% one value, `agent_group_name` 98.8% one value.

## 3 · Does DSAT track longer turnaround?

**No.** This was worth testing and the answer is clean.

| Scale | Spearman with turnaround | n |
|---|---:|---:|
| CSAT code | **0.065** | 3,274 |
| Effort code | **0.055** | 3,233 |

Median days to close moves only **2.1 → 3.3** across the entire satisfaction range. The mean gap
(3.7 → 8.3 days) is a right tail of outliers, not a shift in the typical ticket. Both correlations
are statistically detectable only because n is large; they explain well under 1% of variance.

Independently corroborated by the customers themselves: of 206 dissatisfied-and-high-effort
respondents, **3 chose "Delayed Response"** as their reason.

Detail in `tat_by_score` and `tat_vs_satisfaction_test`.

## 4 · Matched positive-CSAT comparison

`side_by_side` — 30 pairs. Each dissatisfied ticket sits beside a satisfied one matched on contact
reason (level 2), resolution code and a turnaround caliper. **25 matched exactly**, 1 with the
caliper relaxed, 4 at contact-reason level 1 because no satisfied ticket exists anywhere with that
level-2 reason (`Abstract`, `Missing Article(s)`). `match_tier` records which, so weaker pairs can
be discounted. Median turnaround gap within a pair: **1.11 days**.

## 5 · The 1LS rejections — the core question

First, a framing point: **this is not a subset.** `agent_group_name` is a single value for 100% of
survey respondents and every resolution code is a rejection. Every ticket here is a 1LS refusal.

### (i) Could we have made the process easier?

**Mostly no.** Asked to name the single change that would most have reduced the customer's effort —
with an explicit option to answer "nothing" — the review returned:

| | tickets | |
|---|---:|---:|
| **nothing — the process was already direct** | **238** | **88%** |
| giving the reason with the refusal | 5 | |
| answering the actual question first time | 7 | |
| directing the customer to the right team sooner | 2 | |
| not asking for information already supplied | 2 | |
| other, one-off | ~18 | |

And the same picture from the other side. What the exchange turned on:

| | hard | mid | easy | total |
|---|---:|---:|---:|---:|
| The decision itself | 75 | 11 | 18 | **104** |
| A product limit | 65 | 10 | 10 | **85** |
| Cannot tell | 30 | 6 | 11 | 47 |
| **The process** | 26 | 2 | 7 | **35 (13%)** |

**The profile is nearly identical whether the customer said it was hard or easy** — "the decision
itself" is 38–39% in every band. Even among people who reported high effort, the exchange turned on
the outcome, not the handling. Process is 13%.

### (ii) Is there anything in our response that makes things worse?

**Yes, and this is where the opportunity is.**

| What the reply did | tickets | |
|---|---:|---:|
| **No reason given for the refusal** | **123** | **45%** |
| Nothing wrong | 85 | 31% |
| No next step offered | 61 | 21% |
| Sent elsewhere to pursue it | 4 | 1% |

Corroborated by the independent effort scoring: among dissatisfied high-effort tickets,
`resolution_transparency` is **opaque on 50%** against 16% corpus-wide — a 3.1× concentration —
and "Repeated issue explanation" appears 4.6× more often than corpus baseline.

**The strongest single finding.** Cross-tabulating what the model saw in the reply against what the
customer said upset them (`llm_vs_customer_reason`):

| Customers who blamed **Policy** (110) | |
|---|---:|
| Received **no reason** for the refusal | **61 (55%)** |
| No next step offered | 20 (18%) |
| Nothing wrong with the reply | 24 (22%) |

The people we would most readily dismiss as "upset we said no" are disproportionately the people
we never gave a reason to.

### And a third thing worth acting on

**111 of 272 (41%) were told to take it elsewhere — 96 of them to the publisher.** The model
rarely flagged this as a *fault* in the reply (only 4 cases), and it is often correct advice. But
it means two in five dissatisfied customers end the conversation with more work to do, not less.
That is what the corpus-wide "Redirected to another party" flag has been pointing at, and it is
the most likely explanation for the 5,890-versus-600 escalation gap in question 1.

---

## 7 · The mirror image — satisfied *despite* high effort

`read_these_30_satisfied` and `satisfied_vs_dsat`.

**First, the scarcity is the finding.** Only **13 tickets in the entire corpus** — 0.4% of
respondents — are both satisfied (CSAT 1–2) and genuinely hard (effort 4–5). Thirty could not be
drawn from that cell, so the sample is banded and every row says which band it came from:

| Band | | in corpus | taken |
|---|---|---:|---:|
| A | Satisfied (1–2), genuinely hard (4–5) | 13 | **12** |
| B | Positive (3), genuinely hard (4–5) | 11 | **10** |
| C | Satisfied (1–2), effort neutral (3) | 48 | 8 |

Band C is filler to reach the 30 asked for; it is excluded from the comparison below so it cannot
flatter the contrast. Three A/B tickets have no transcript.

**The difficulty was real.** The LLM effort score, computed independently of the survey, rates
**62%** of the satisfied-but-hard group high effort against **59%** of the dissatisfied-and-hard
group. These customers were not quietly having an easy time — the interactions were comparably
hard and they were happy anyway.

**What differs, on 22 tickets:**

| | Satisfied despite hard (22) | Dissatisfied and hard (206) |
|---|---:|---:|
| Reply **opaque** | 33% | **50%** |
| Reply transparent | 19% | 11% |
| Friction: repeated issue explanation | 14% | **25%** |
| Friction: escalation required | 9% | **18%** |
| Reply gave no reason | 41% | 49% |
| Nothing wrong with the reply | 32% | 28% |

**Read this cautiously.** At n=22 a 95% interval on any of these percentages is roughly ±20 points,
so none of the gaps is individually conclusive. What is worth noting is that every gap points the
same way — the satisfied group got clearer replies, re-explained themselves less, and were escalated
less — and that the two largest gaps are the same two measures that separate dissatisfied tickets
from the corpus baseline. That is consistent with the main finding rather than independent evidence
for it.

The measures that do *not* differ are as informative: "no reason given" is 41% versus 49%, and
"nothing wrong with the reply" 32% versus 28%. On those, the two groups are indistinguishable.

## What I would do with this

1. **Require a reason with every refusal.** 45% currently lack one, and among Policy complaints
   55% do. This is a template and QA change, not a policy change.
2. **Require a next step**, even when the answer is no — where to go, what would change the answer,
   who decides.
3. **Do not invest in speed.** Turnaround does not track dissatisfaction in this corpus, and only
   3 of 206 customers raised it.
4. **Look hard at the publisher redirect.** 96 tickets end with "contact the publisher". Some are
   unavoidable; a warm handoff or a clear explanation of why we cannot act would land differently.

## Limitations

- Survey respondents are **5.6%** of tickets and self-selected.
- CSAT and effort correlate at **Spearman 0.731**, so hard-versus-easy separates degrees of one
  reaction more than two independent signals.
- Only the **rejected half** of the outcome space exists here. No actioned ticket is available, so
  "could this have been actioned instead" cannot be answered from this data.
- The structured read is a single LLM pass, blind to the survey scores but unvalidated against a
  human reviewer. The 30-ticket sample exists so you can check it.
- **13 of the 286** dissatisfied tickets have no transcript and were not reviewed.
- `dr_driver` coded only 1 ticket as "how it was explained" despite 123 flagged "no reason given"
  on the wording field — it anchors on the substantive dispute, so read the two together.
- Corpus is **seven months** (Jan–Jul 2026), not a year.
