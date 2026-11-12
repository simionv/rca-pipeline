# Stakeholder Q&A — *Why Scopus content requests are rejected*

Companion to `runs/output/CSD_2026_validation_rules_analysis.pptx` and `docs/CSD_2026_deck_talking_points.md`.

**How to use this.** Every entry has the same shape:

- **The question** as it will actually be asked, not as it would be written down.
- **Short answer** — one or two sentences. This is what you say first. If the room accepts it, stop there.
- **The full answer** — the detail, for when they don't.
- **If pushed** — the follow-up you will get, and what to do with it.

**Three rules for the room:**

1. **Never defend a number you haven't got.** Every honest "I don't know, and here's what it would take to find out" is worth more than a confident guess that gets checked afterwards.
2. **Lead with the concession.** On the four or five questions where the criticism is fair — reference standard, effort reliability, survey self-selection, prompt tuning — say the weakness before they finish asking. It ends the exchange instead of extending it.
3. **Separate "the matrix is wrong" from "the measurement is wrong".** Most challenges are attempts to reclassify a policy finding as a data-quality problem. Slides 5, 8 and 34 are how you keep them apart.

---

# 1 · Trust in the method

### Q1.1 "How do we know the AI got this right?"

**Short answer.** We don't know it got every ticket right, and the deck never claims that. What we know is how often its answer matches the code the agent logged — 79.9% among comparable tickets — and we know that number was produced without the model ever seeing the code.

**The full answer.** There are four separate safeguards, and it's worth naming them in order because they answer different worries.

*Blindness.* The input file given to the model had two columns: ticket ID and conversation text. No resolution code, no metadata. We verified this by reading the header of the file as it sat on disk, not by trusting the code that wrote it — and one ticket was thrown out entirely because the agent had pasted the resolution code into the reply text. If the model could see the answer, the 79.9% would be worthless.

*Grounding.* Every classification comes with a verbatim quote from the transcript that the model says justifies it. We check that the quote actually appears in the source text. A model that invents its evidence fails this check, and it's one of the smoke-test gates.

*Staged validation.* 40 tickets, then 1,000 tickets three times, then 12,000. Each gate had pass criteria set before the run, not after.

*Independent corroboration.* The rejection reasons were discovered bottom-up from the tickets, with no reference to the matrix. They align with the rules at 0.42 on a 0-to-1 association scale — related but genuinely independent. Two independently derived labels pointing the same way is stronger evidence than either alone.

**If pushed — "but you can't verify it without humans reading tickets."** Correct, and that's the gap. There is no human-adjudicated gold set for this corpus. We put 30 disagreement cases into the deliverable workbook with both justifications side by side precisely so that someone can start building one. Two hours of a Content specialist's time would tell us whether the disagreements are model error, agent error, or matrix silence — and right now nobody knows the split.

---

### Q1.2 "Why should I trust a model that changes its mind? Slide 54 says it only agrees with itself 62% of the time."

**Short answer.** That 62% is the *effort* score, not the rule classification, and the distinction matters a great deal.

**The full answer.** Slide 54 measures the customer-effort score — a subjective five-point judgement about how hard an interaction felt. Two runs of that agree exactly 62.3% of the time and within one level 98.4% of the time. So the disagreements are almost entirely "medium versus high", not "very low versus very high". That's the profile you'd expect from a genuinely ordinal judgement with fuzzy boundaries, and honestly it's the profile you'd get from two human raters too.

The rule classification is a different kind of task: it's a choice among 25 discrete, defined categories with an explicit "none applies" option, and every answer is anchored to a verbatim quote. **We have now measured it too: 70.1% agreement** across all 12,000 tickets. Better than the effort score, and still meaning the classifier picks a different rule on roughly three tickets in ten.

**The honest reading of that 70%.** It is a *lower* bound on same-prompt repeatability, because the second pass used a different prompt — a multi-label one asking which rules apply, with its best-fit answer compared against the original. Some of the 30% disagreement is that prompt difference rather than instability. A same-prompt re-run would land higher, and we have not done one.

What it bounds, and what it doesn't: it bounds confidence in any *individual* ticket's rule, and it bounds the precision of the small per-rule figures in the appendix. It does not undermine the aggregates — a rate over 12,000 tickets is far more stable than any single label, and the headline conformance figure carries its own sampling interval on top.

**If pushed — "so which findings survive that?"** Findings 1 and 2 are untouched: they are arithmetic on resolution codes and the matrix, not on the classifier. Finding 3 is checkable by hand. The 79.9% conformance figure and every per-rule rate are the ones to read with the 70% in mind.

---

### Q1.3 "You tuned the prompt three times until you got a number you liked."

**Short answer.** We tuned it three times, the headline moved from 67% to the high seventies, and we stopped when further changes fell inside the statistical noise of the test — not when the number looked good. The full record is on slide 61.

**The full answer.** Each of the three corrections fixed a specific, nameable defect that we could point at in the transcripts:

1. The model was treating a standing boilerplate disclaimer — "any journal may be subject to re-evaluation at any point in time" — as positive evidence that the journal was under re-evaluation. It appears at the bottom of most coverage replies. False positives on disclaimer-only tickets: 44% → 24%.
2. The model was confusing the generic indexing timeline ("please allow 6 weeks") with the specific pipeline rule ("your article has been received and will appear within days"). Rule 05 recall 49% → 89%, rule 07 precision 37% → 73%.
3. The model was routing discontinued titles to the re-evaluation rule instead of the coverage-mismatch rule. 23/70 correct → 56/70.

Every one of these is a factual error you can verify by reading the tickets. None of them is "the number was too low".

The stopping rule is the important part. A 1,000-ticket probe has a sampling interval of about ±3.1 points. Once round-three-versus-round-two differences fell inside that band, further tuning would have been fitting to noise. We stopped there.

**If pushed — "how would we know if you'd overfitted?"** You'd expect the main run on 12,000 to come out materially better than the probes if we'd fitted to the probe tickets. It didn't — the headline landed inside the probe range. That's weak evidence, not proof. Strong evidence would be a held-out set that was never used for tuning, which we did not construct and should have.

---

### Q1.4 "Which model was this, and does that matter?"

**Short answer.** A single large language model, one pass per ticket, no ensemble and no second opinion. It matters mostly for reproducibility.

**The full answer.** The whole run is a single model, single pass. That's on slide 62 as a stated limitation. Three consequences worth being explicit about:

- **No self-consistency check.** Running the same ticket three times and taking a majority would reduce the variance we see on slide 54. We didn't do it because it triples the cost, and at the aggregate level the variance mostly averages out.
- **Model version drift.** If the underlying model is updated, re-running will not reproduce these exact numbers. Everything else — the sample, the seed, the taxonomy, the prompts — is pinned and versioned.
- **No cross-model check.** We don't know whether a different model would find the same gaps. My expectation is that findings 1 to 3 would survive any model, because they're driven by resolution-code counts rather than by classification — 9,585 is a count, not an inference. The conformance rate itself would move.

---

### Q1.5 "This is just an AI grading the humans. Why is its opinion worth anything?"

**Short answer.** It's not grading anyone. It's reading what was written and asking which policy that matches — and where it disagrees with the agent, the deck says explicitly that either side can be wrong.

**The full answer.** Slide 8 exists for this question. The resolution code is one agent's choice at close, under time pressure, from a list where "Others" carries 3,904 tickets a year and functions as a wastebasket. We use it as the reference because it's the only pre-existing label on all 56,935 tickets and it was produced independently — not because it's correct.

The word "conformance" was chosen deliberately over "accuracy". Conformance means: do these two independent descriptions of the same ticket agree? When they don't, slide 40 lists three possible explanations and states that the analysis cannot distinguish them.

And the findings that matter least depend on the model at all. Finding 1 — 9,585 tickets whose code no rule claims — is pure arithmetic on the resolution code and the matrix. It would be true if we had never run a classifier.

**If pushed — "so the agents aren't being judged?"** No. Nothing in this deck is by agent, by team, or by individual, and the data was never cut that way. If anyone asks for that cut, my recommendation is to decline until the reliability questions in section 1 are settled.

---

# 2 · Sampling and extrapolation

### Q2.1 "Why 12,000? Why not all of them?"

**Short answer.** Because 12,000 gets the headline to ±0.6 percentage points, and no decision on the table changes between 79.9% and 79.6%. The full run would cost $695 and buy precision nobody would use.

**The full answer.** Precision improves with the square root of sample size. Going from 12,000 to 50,714 would take the interval from about ±0.6 to about ±0.0 — the finite-population correction means a census has no sampling error at all. But look at what actually depends on those decimal places: swapping rule 08's primary code, adding an enquiry rule, drafting an AiP rule. None of them turns on a fraction of a point.

There is one genuine reason to run the full corpus, and it's on the recommendations slide: if you want a validation-rule tag on every individual ticket for operational routing or reporting, you need every ticket tagged. That's a different project with a different justification, and it should be scoped after the matrix is revised so you're not tagging against a matrix you're about to change.

---

### Q2.2 "Is 12,000 tickets actually representative?"

**Short answer.** Not by design — it deliberately isn't, and that's why we weight. After weighting, it represents the 50,714 classifiable tickets correctly.

**The full answer.** The sample was stratified by resolution code with a floor of 300 per code. So rare codes are massively over-represented relative to their true share, and large codes are under-represented. Raw sample percentages therefore do *not* describe the population, and the deck never presents them as if they did — every results table shows sample and population side by side precisely so you can see the difference.

The weighting undoes it. Each ticket gets a weight of N over n for its own code — how many population tickets it stands for. Weights range from 1.00 to 5.27 and sum to exactly 50,714, which is checked arithmetically on every run.

Slide 18 shows what happens if you skip this. "Invalid- Non-GenCAR": 307 in the population, 301 sampled. A flat 4.227× multiplier gives 1,272 — four times the number that exist. Across individual rules and reasons the naive error runs from −20% to +50%.

**If pushed — "representative of what, exactly?"** Of the 50,714 classifiable 2026 tickets. Not of the 56,935 in the file, not of 2025, and not of other Elsevier products.

---

### Q2.3 "You threw away 6,214 tickets. What if they're the interesting ones?"

**Short answer.** They may well be, and we say so on slide 14 — but the bias runs *against* our conclusions, not towards them, so the gaps are if anything understated.

**The full answer.** The exclusions break down as 5,844 chat threads whose transcript was never captured, 369 tickets with under 300 characters of text, and 1 ticket that quoted its own resolution code.

They are demonstrably not random. Advice requests are excluded at 33.9%; Not-Missing at 3.7% — nine times the rate. That's the whole point of slide 14.

Now trace the direction. Advice requests are the largest unmapped code (finding 1) and the group least likely to have a rule. They're also the most excluded. So the tickets we couldn't classify are disproportionately the ones that would have made the coverage gap look *larger*. Our known bias understates finding 1.

That's the right way round. If our bias inflated our headline finding, you should discount it. It deflates it.

**If pushed — "can you quantify the understatement?"** Not without classifying them, and we can't classify them — there's no text. What we can say is that the exact counts on slide 34 are counts of *classifiable* tickets. Against the whole 56,935 file, advice request is 8,069 rather than 5,332. The uncovered volume is larger; we just can't put a rule-level breakdown on the difference.

---

### Q2.4 "What does ±0.6% actually mean? Is that the error bar on everything?"

**Short answer.** No. It's sampling error only — the uncertainty from having measured 12,000 tickets instead of all 50,714. It does not include model error, agent error, or the excluded tickets.

**The full answer.** Read it like this: if we redrew the sample the same way many times, 95% of those samples would put the true population rate between 79.3% and 80.5%.

What's inside that interval: the luck of which tickets got drawn.

What's outside it, and unquantified: whether the model classified correctly; whether the agent logged the right code; whether the 6,214 excluded tickets would have behaved differently; whether the model would give the same answer on a re-run.

The interval is narrow because 12,000 out of 50,714 is a big sample and the finite-population correction is doing real work. Narrow sampling error on a measurement with unquantified systematic error is a familiar trap, and the honest framing is: *we are confident about the arithmetic and appropriately unsure about the labels.*

---

### Q2.5 "Why does the mappable share have ±0.0%? That looks like a mistake."

**Short answer.** It's correct. Whether a code is claimed by some rule is a fact about the matrix, not something we estimated, so once you know each ticket's code it's a weighted count with no sampling uncertainty.

**The full answer.** Every ticket's resolution code is known for the whole population — it's metadata, not a classification. And whether that code appears as a primary code somewhere in the matrix is a lookup. So the share of tickets with a mappable code is computed exactly. The weighting rearranges known quantities; it doesn't infer anything.

Contrast that with conformance, which depends on the model's rule assignment. That *is* estimated from 12,000 tickets, and carries an interval.

The rule of thumb from slide 21: if a figure is defined by a resolution code, it's an exact count. If it's defined by our classification, it's an estimate with a ±.

---

# 3 · The conformance numbers

### Q3.1 "Is 79.9% good or bad?"

**Short answer.** There's no benchmark to compare it against, so on its own it's neither. What makes it useful is that findings 1 to 4 account for most of the missing 20 points — meaning the shortfall is explained and addressable rather than mysterious.

**The full answer.** Nobody has measured this before, on this corpus or any comparable one, so there is no industry number and no prior year. Treat 79.9% as a baseline that future measurements move against.

Where it becomes informative is in the decomposition. Of the tickets that don't conform:

- A large share are rule 08 tickets logged as "discontinued title" — which is a mapping-table defect, fixable by editing one cell (finding 2).
- A further share are AiP tickets with no general rule to route to (finding 3).
- Others are genuine classification disagreement, and slide 40 says we can't attribute them.

So the interesting question isn't "is 79.9% good", it's "how much of the 20.1% is a matrix defect and how much is a measurement defect". Best current estimate: fixing rule 08 alone accounts for roughly 3,500 tickets a year.

**If pushed — "what would good look like?"** I'd set the target on the components, not the headline. After the rule-08 swap and an enquiry rule, matrix code coverage should exceed 90% and strict conformance should follow. That's a target you can hold someone to; "get to 85%" isn't, because it could be reached by tuning the prompt.

---

### Q3.2 "Why are there three different conformance numbers? Which is the real one?"

**Short answer.** All three are real; they have different denominators and answer different questions. Quote the headline for classification quality, strict for end-to-end policy coverage — and never quote either without its denominator.

**The full answer.**

| Rate | Question it answers | Value | Max possible |
|---|---|---:|---:|
| Strict | Of all rule-tagged tickets, how many carry the rule's designated primary code? | 64.8% | 81.1% |
| Loose | Same, but also counting the matrix's own "also maps to" codes | 71.5% | 81.1% |
| **Among mappable (headline)** | Of tickets that *could* match a rule's code, how many do? | **79.9%** | 100% |

Strict has a maximum below 100% because a ticket whose code no rule claims can never conform, however well the classifier performs. That's a matrix property, not a measurement property, and mixing it into a performance number makes the number uninterpretable.

The headline strips it out: restrict to tickets that can conform, then ask how often they do.

They're internally consistent: 81.1% × 79.9% = 64.8%. If those didn't multiply out, one would be wrong.

---

### Q3.3 "77.4% coverage and 79.9% conformance — so you've basically hit the ceiling?"

**Short answer.** No — that's a denominator confusion, and it's the single most common misreading of this deck. The headline's ceiling is 100%, not 77.4%.

**The full answer.** The two numbers count different things over different sets.

**Matrix code coverage (77.4%)** is the share of all tickets whose resolution code appears as some rule's primary. It's a property of the matrix. It would be 77.4% if we'd never classified anything.

**Conformance among mappable (79.9%)** is measured *only* on tickets whose code a rule claims. Tickets outside the 77.4% are excluded from its denominator before the calculation starts. So the 77.4% cannot bound it.

What 77.4% *does* bound is the strict rate, which is measured over all rule-tagged tickets including unmappable ones. And indeed strict sits at 64.8%, comfortably below.

The headroom on the headline is 20.1 points, and that headroom is the disagreement worth investigating.

**Why this comes up.** The two numbers are close together and both look like percentages of the same thing. Slide 10 exists solely to separate them. If it comes up in the room, the one-sentence version is: *one counts tickets the matrix can't reach, the other counts tickets it reached and got wrong.*

---

### Q3.4 "You're proposing to change the target so the number improves. Isn't that gaming it?"

**Short answer.** The strict rate stays in the deck, both are reported side by side, and the argument for the change is evidential: 3,684 agent decisions are better evidence of practice than one cell in a mapping table.

**The full answer.** This is the fair-minded version of the rule-08 objection and it deserves a real answer.

The matrix says rule 08's primary code is "Out of coverage". Across all of 2026 that code was used 59 times. The tickets rule 08 actually describes carry "discontinued title" — 3,684 of them. And "discontinued title" is already in the matrix on rule 08's row, as an "also maps to".

So the choice is between two readings. Either 3,684 tickets a year were miscoded by agents and 59 were right — in which case there's a substantial training problem nobody has noticed. Or the mapping table has the primary and the secondary the wrong way round.

The second is far likelier, and it also matches the qualification the matrix puts on itself. Its own Legend sheet says: *"Rule->code and rule->template links reflect standard CSD practice and involve interpretation; validate against current CCG/CAR before operational use."* The matrix is telling you these links are interpretive.

The safeguard against gaming is that we report both rates permanently. Slide 35 shows 2.2% strict and 84.7% loose next to each other. Nothing is being hidden by the recommendation.

**If pushed — "who decides?"** Content policy. This is a recommendation with the evidence attached, not a change we can or would make.

---

### Q3.5 "Rule 06 conforms at 95% but rule 11 at 2%. Doesn't that mean the classifier is unreliable?"

**Short answer.** It means the *rules* differ in how well their designated code matches practice. Both high and low figures are informative, but read the low ones alongside their sample size.

**The full answer.** Conformance per rule is a joint property of three things: how distinctive the rule is in the transcript, how well its designated code matches what agents actually pick, and how many tickets it has.

Rule 06 at 95% is distinctive (the agent says the paper is already in Scopus), and its code, "Not Missing", is unambiguous.

Rule 11 at 2% strict / 16% loose sits on 58 tickets, and its designated code is "Not within scope" — which appears 200 times in the whole year. It's the same structural problem as rule 08, just smaller: a designated code that is barely used. Worth flagging to Content as a second instance of the pattern.

The estimability flag on slides 57–58 is the guard here: anything under 30 sampled tickets is marked *not estimable* and should be read as illustrative only. Rule 19 has one ticket. Its 0% is not a rate.

---

# 4 · The findings

### Q4.1 "We already knew the matrix had unmapped codes. What's new?"

**Short answer.** The size. The matrix flagged the gap qualitatively; this puts 9,585 tickets a year against it and tells you which three codes and in what proportion.

**The full answer.** The workbook has a sheet called "Unmapped 'invalid' res codes", so the authors knew. What they couldn't do was size it, because sizing needs the resolution-code distribution joined to the matrix across a full year.

What's new:

- **The volume split.** Advice request 5,332, discontinued title 3,684, book 569. Very different problems needing very different fixes.
- **The AiP finding**, which is *not* in that sheet. AiP is a mapped code — rules 14 and 22 claim it. But both are narrow special cases, so the general case has no rule despite the code being covered. Only a ticket-level read finds that.
- **The effort overlay.** Tickets with unclaimable codes run 38.9% high-effort against a 21.3% baseline. The gaps aren't just untidy; they're where customers struggle.
- **17 drafted candidate rules**, with volumes attached.

---

### Q4.2 "Advice requests aren't really rejections — should they even be in scope?"

**Short answer.** They're coded "Invalid- advice request", so operationally they are rejections. Whether they *should* be is a genuinely open policy question and one of the more interesting things the analysis surfaces.

**The full answer.** 8,069 in the full year, 5,332 classifiable. Every one closed with a code beginning "Invalid-". They're in scope because the corpus is defined by that prefix.

But when you read them, most are enquiries — "is my journal still indexed?", "when will this appear?" There's no request to invalidate. That's why no rule fits: every rule in the matrix is phrased about a request to add, correct or change something.

So there are three possible responses and they're for Content, not for us:

1. Write validation rules that apply to enquiries. Awkward — an enquiry can't really be "invalid".
2. Create a non-Invalid disposition for enquiries answered correctly. Cleanest conceptually, but it changes the reporting baseline: about 8,000 tickets a year stop being "invalid" and volume trends break.
3. Leave it, and accept that a sixth of the corpus sits outside the governance framework.

Worth noting that advice requests are also the most-excluded group (33.9% unclassifiable), so whatever is happening there, we see it least well.

---

### Q4.3 "Can we just adopt the 17 proposed rules?"

**Short answer.** No. They're evidence that rules are needed, at a specific volume, with a starting draft — the wording is not validated and the deck says so.

**The full answer.** The "model agreement" column on slide 39 is how consistently the same wording came back across tickets of the same kind. The best candidate is 17%; every one on the slide is under 10%.

Low agreement means the model recognised the *gap* consistently but expressed it differently each time. So:

- **Trust the gap.** It's defined by tickets no existing rule covered — that part is solid, and the volumes are design-weighted like everything else.
- **Don't trust the wording.** At 9% agreement, the phrasing is essentially one draft among many the model could have produced.

The right process: Content reads them as a prompt for discussion, decides which gaps are real, and writes the rules in the matrix's own register with the CCG/CAR references attached. All 17 with supporting tickets are in `runs/output/csd_2026_rule_proposals.xlsx`.

**If pushed — "how long would that take?"** Realistically a workshop per gap cluster. The four biggest — enquiries, discontinued titles, AiP, books — are probably a day between them, because the policy questions are clear even if the wording isn't.

---

### Q4.4 "Finding 3 says the classifier routes AiP tickets to the wrong rule. Isn't that a bug you should have fixed?"

**Short answer.** We could have, and chose not to, because fixing it would have hidden the finding rather than resolved it.

**The full answer.** The situation: 1,534 tickets a year carry the AiP resolution code. Rule 14 covers MEDLINE-sourced AiP and unapproved publishers. Rule 22 covers missing volume/issue/page on an AiP. A customer who says "my article is in press and isn't in Scopus yet" fits neither, and the classifier routes them to rule 05 — too recent — which is a defensible reading of what the transcript says.

We could have added a prompt cue: "if the ticket mentions Articles in Press, prefer rule 14." Conformance on the AiP code would have jumped. And the crosstab would then have shown AiP tickets flowing correctly to rule 14 — a picture that is wrong but looks right, and that would have concealed the fact that the matrix has no general AiP rule.

Choosing the honest crosstab over the better number is the same choice as reporting the effort-score reliability on slide 54. Both cost us on the surface and both are why the rest is trustworthy.

---

### Q4.5 "What if a ticket breaks more than one rule? You only recorded one."

**Short answer.** Fair challenge, and we went and measured it: **2.3% of tickets break two rules, none break three**. Slide 37.

**The full answer.** The main classifier is single-label by design — one rule per ticket — so on its own it genuinely could not answer this. We ran a separate pass over the same 12,000 tickets with a different question: not "which rule fits best" but "which rules apply". Results:

| | |
|---|---:|
| Exactly one rule | 97.7% |
| Two rules | 2.3% (320 of 11,971; unweighted 2.7%, Wilson CI 2.4–3.0%) |
| Three or more | 0% |

**The useful part is where the overlap sits.** Rule 08 is involved in **68%** of every multi-rule ticket. It pairs with rules 01, 02, 03, 05 and 06 — because its condition, *pre-dates coverage start or falls after the last covered year*, can be true alongside almost any other. That is a third independent line of evidence pointing at rule 08, after Finding 2 and the discontinued-title deep dive. All 38 observed pairs are in `runs/output/csd_2026_multi_rule_analysis.xlsx`.

**If pushed — "so the single-label design was fine?"** On this corpus, largely yes: 97.7% of tickets have one answer, so forcing a single choice loses very little. But say the caveat before it is found. The 2.3% is a **lower bound**, because 8 of the 25 rule descriptions carry single-label wording — "not this rule", "do not use" — that we added during the original prompt tuning. The taxonomy actively discourages double-labelling, so a taxonomy written for multi-label use would likely find more.

**The uncomfortable number on that slide.** The second pass agreed with the original run on only **70.1%** of tickets. That is the rule classifier's test-retest figure, and it means the classifier disagrees with itself about ten times more often than tickets break two rules. It bounds confidence in any individual ticket's rule and in the small per-rule appendix figures; it does not undermine the aggregates, which are far more stable. See Q1.2.

---

### Q4.6 "Which recommendation should we do first?"

**Short answer.** Rule 08's code swap. Highest volume, lowest cost, no operational change, and it moves ~3,500 tickets a year from non-conforming to conforming without touching a ticket or retraining an agent.

**The full answer.** In order of value per unit of effort:

1. **Rule 08 code swap** — 3,684 tickets/yr. One cell in a mapping table. The evidence is unambiguous: 59 versus 3,684.
2. **The 30 disagreement cases** — costs two hours of a Content specialist's time and tells you whether the 20% disagreement is model error, agent error, or matrix silence. Nothing else in the deck is that cheap or that informative.
3. **An enquiry disposition** — 5,332 tickets/yr, the biggest gap, but it's a design question rather than a fix, so it needs a decision before it needs work.
4. **A general AiP rule** — 1,534 tickets/yr, narrow and self-contained.
5. **The 17 candidates** — 7,696 tickets/yr, but the largest workload and it partly overlaps with 3 and 4.

I'd deliberately *not* start with the full-corpus re-run. Tagging every ticket against a matrix you're about to change wastes the run.

---

# 5 · Customer effort (Part F)

### Q5.1 "How can an AI know how much effort a customer put in?"

**Short answer.** It can't know — it reads what the customer wrote and judges from it. That's why the deck calls it *judged* effort, keeps it separate from the measurable *observed* effort, and validates both against actual survey answers on slide 53.

**The full answer.** Three distinct things, and keeping them apart is the whole design.

*Observed effort* is arithmetic on the thread record: turns, distinct agents, elapsed time, whether the customer raised another ticket. Exact, no model, all 56,935 incidents. It knows how the interaction unfolded and nothing about how it felt.

*Judged effort* is the model reading the transcript and rating effort on five levels, with friction points, themes and a transparency judgement, each grounded in a verbatim quote. It reads tone, repetition, frustration, being passed around. It's blind to anything not written down — a customer who gave up silently looks easy.

*The customer's own answer* is the CSAT survey effort question. 2,813 people. This is the only ground truth in Part F and it's the reason slide 53 exists.

The result on slide 53 is that the model's reading correlates with the customer at +0.207 while the best handling metric manages +0.112. Both are modest. The model is roughly twice as informative, and the comparison is fair because it's the same 2,813 people for every signal.

---

### Q5.2 "+0.207 is a weak correlation. Why present it at all?"

**Short answer.** Because everything it's compared against is weaker, and because the ceiling on any correlation here is +0.675 — the score's agreement with itself.

**The full answer.** Two things make a modest number meaningful.

*The relative comparison.* The alternatives on the same 2,813 customers: customer turns +0.112, span +0.085, total turns +0.078, composite index +0.056, first response +0.031, repeat contact −0.009, agent handoffs −0.028. The last two are negatively signed and indistinguishable from zero. Whatever +0.207 is, it's roughly double the best alternative and the only one clearly above the noise.

*The reliability ceiling.* A measure can't correlate with anything better than it correlates with itself. Test–retest here is +0.675. Standard attenuation correction puts the true relationship nearer +0.25. Still moderate — but the instrument, not the underlying relationship, is a large part of what's limiting it.

And there's a third point that's easy to miss: customer-reported effort is itself noisy. A single survey question answered days later is not a precise instrument either. Some of the missing correlation is on their side of the comparison.

**If pushed — "so it's not much use."** For an individual ticket, correct — don't use it. For ranking rejection reasons or rules by how hard they are, it's fine, because aggregation averages the noise away. Use it for prioritisation, not for triage.

---

### Q5.3 "You're saying our operational metrics are wrong. That's a big claim."

**Short answer.** The claim is narrower than that: on this corpus, against these 2,813 customers, handoffs and repeat contact do not track customer-reported effort. It's a finding about these metrics in this context, not a general law.

**The full answer.** Take the caveats seriously and state them yourself.

- 2,813 self-selected survey responders. People who answer surveys differ from those who don't, and we haven't corrected for it.
- One product, one year, and only rejected tickets. Every ticket in this corpus ends in a no, which compresses the range of outcomes.
- Correlation against one survey question.

With those in place, the finding stands: agent handoffs correlate at −0.028 and repeat contact at −0.009 against what the customer said. Both intervals straddle zero. On this corpus they carry no information about customer effort.

A plausible mechanism, and worth offering: complex cases get handed to specialists *and* get resolved better, so handoffs mix "we passed you around" with "we found the right expert". Those pull in opposite directions and cancel.

What follows is narrow: if a dashboard reports customer effort as a function of handoffs and repeat contact, that dashboard should be checked against survey data before its numbers are acted on. Not "operational metrics are useless" — they're excellent for capacity, cost and SLA. They're just not a proxy for how hard it felt.

---

### Q5.4 "You added a friction category the standard taxonomy doesn't have. Doesn't that break comparability?"

**Short answer.** Yes, and deliberately — the standard eight had no category for being told to take your request elsewhere, which is 12% of this corpus and 86% high-effort when it happens.

**The full answer.** The eight standard categories were designed for a general support corpus. This corpus is entirely rejections, and one of the most common rejection experiences is being redirected — to the publisher, to the journal, to the editor, to another team. Without a category for it, those tickets scatter across "process complexity" and "escalation required" and the pattern disappears.

With the category: 1,706 sampled tickets, 6,126 a year, and 86% of them judged high effort. That's the second-strongest friction marker in the analysis and none of the original eight would have surfaced it.

On comparability — the eight originals are unchanged, so any comparison restricted to them still works. The ninth is additive.

There's a related point worth raising as information rather than as a complaint: friction normalisation existed in the codebase but had never run, because the category list was missing from the configuration. So earlier effort analyses in this repository had unnormalised friction points scattered across spelling variants. This is the first run where normalisation was actually active. Anyone maintaining downstream effort reporting should know.

---

### Q5.5 "Does slide 51 mean fixing the matrix will reduce customer effort?"

**Short answer.** No. It's a correlation, and the more likely mechanism is that hard cases are both harder to classify and harder to resolve. Fixing the matrix will not, by itself, make customers' lives easier.

**The full answer.** The numbers: 21.3% high-effort where rule and code agree; 35.0% where they disagree; 38.9% where the code is one no rule can claim.

Three readings, and we can't distinguish them:

1. *Common cause* (most likely). Ambiguous, complex tickets are hard to fit to a rule and hard to resolve. The matrix gap and the effort share a cause rather than one causing the other.
2. *Causal* (possible, partial). No rule means no template, so agents improvise, replies get slower and less consistent, and the customer feels it. Plausible for the enquiry cluster in particular.
3. *Reverse.* Long, messy tickets produce more text, more contradictory signals, and therefore more classification disagreement.

What the finding *does* establish is co-location: the matrix's blind spots and the customer's hardest experiences are in the same tickets. That's a good reason to prioritise those gaps. It is not a promise that closing them moves an effort metric.

**If pushed — "how would you test causality?"** Fix rule 08, wait two quarters, and compare effort on discontinued-title tickets before and after with everything else as a control. That's a real experiment and it's worth doing — but it takes six months, not a slide.

---

### Q5.6 "Why is the effort score in the deck at all if it's only 62% repeatable?"

**Short answer.** Because it's the best available signal — twice as informative as anything in the handling record — and because rankings survive noise that point estimates don't.

**The full answer.** Distinguish three uses.

*Individual tickets.* Don't. 62.3% exact agreement means a given ticket's score could plausibly have come out one level different. Slide 54 says this explicitly.

*Aggregate rates.* Use with a wide margin. The two runs put the high-effort rate at 34.4% and 30.7% — 3.7 points apart. Say "roughly a quarter to a third", never "27.3%".

*Rankings.* This is where it earns its place. "Content Format Issues at 60% versus Duplicate Requests at 0.6%" is a gap of sixty points; a few points of noise doesn't touch it. Every conclusion in Part F is a ranking: which reasons are hardest, which rules, which signals track the customer best.

And the alternative isn't a better measure — it's no measure. The handling metrics are worse. The survey covers 5% of tickets and only arrives afterwards. A noisy signal that ranks correctly beats a precise signal that measures the wrong thing.

---

### Q5.7 "You have survey data on slide 53 — why not use it for everything?"

**Short answer.** It covers about 5% of tickets, only those where someone chose to respond, and it arrives after the fact. It's the right validator and the wrong primary measure.

**The full answer.** 2,813 responses against 50,714 classifiable tickets. Three limits:

- **Coverage.** 5%. Any breakdown by rejection reason lands on 44 to 187 respondents per reason, and all six reason-level correlations have intervals that span zero. Not enough to act on.
- **Self-selection.** People who respond are systematically different — typically more polarised. Uncorrected here.
- **Timing.** Post-hoc. Useless for anything operational.

The right division of labour is what the deck does: the survey validates the LLM score, and the LLM score — available on every ticket, immediately — does the work.

**If pushed — "so extend the reasons to all 50k and get more survey overlap per reason."** That doesn't help as much as it sounds. Survey coverage stays at 5% of whatever you tag, so a reason with 187 respondents today gets roughly four times that only if you also quadruple the tagged tickets — about $530 to run rules and reasons over the remaining 38,721. Worth doing if per-reason survey calibration is the goal; not worth it for anything else in this deck.

---

# 6 · Cost, scope and what happens next

### Q6.1 "What did this cost?"

**Short answer.** $242.52 for the rules and reasons analysis, plus $416 for customer effort. About $660 in model spend, plus analyst time.

**The full answer.** Rules and reasons (slide 43): $3 discovery, $56 validation gates, $164.33 main run, $8 gap pass — $242.52.

Customer effort: about $86 for the 12,000-ticket run and gates, plus $330 to extend scoring to all 50,721 tickets — $416.

One thing to disclose rather than bury: roughly $80 of that $330 was wasted. The full-corpus run was supposed to reuse the 12,000 tickets already scored and re-scored them instead. The cause isn't diagnosable from the surviving logs. The silver lining is real, though — that accident is what produced the test-retest measurement on slide 54, which is one of the more valuable slides in the deck and which nobody would have paid for deliberately.

---

### Q6.2 "What would it cost to do this every year? Or every quarter?"

**Short answer.** About $250 a year for the same design on rules and reasons, less if the taxonomy is stable. Quarterly on a smaller sample would be around $70 a quarter.

**The full answer.** Most of the $242.52 was one-time: taxonomy discovery, prompt development, three probe rounds. A repeat run against a stable taxonomy is mostly the main run — around $165 for 12,000 tickets, plus a smoke test.

For quarterly tracking you don't need 12,000. 4,000 stratified tickets gives roughly ±1 point on the headline, which is ample for trend, at about $55 a quarter.

What's *not* free is the analyst time: the sample design, the validation gates, and the interpretation. Call it a week per run, less once it's routine.

**If pushed — "should we?"** Only after the matrix is revised. Re-measuring conformance against an unchanged matrix will reproduce the same findings and tell you nothing new. Measure again once something has been fixed, so the number has something to move against.

---

### Q6.3 "Can we use this to route tickets automatically?"

**Short answer.** Not yet, and not on these numbers. Routing needs per-ticket reliability, and we've measured that for effort (62% repeatable) but not at all for rules.

**The full answer.** Three things would have to be true first, and none is today.

1. **Per-ticket reliability is now measured, and it is not good enough for routing.** The effort score agrees with itself 62.3% of the time; the rule classifier, 70.1%. Routing on a label that changes on three tickets in ten would misroute at a rate no service desk would accept. This is the blocker, not a formality.
2. **The matrix complete enough to route into.** Right now 15.2% of tickets have no rule and 9,585 a year have a code no rule claims. Automatic routing would send those somewhere arbitrary.
3. **Human adjudication on a gold set.** We have 30 disagreement cases and no adjudicated ground truth. You cannot commit to a routing accuracy target without one.

The honest sequence is: fix the matrix → build a gold set → measure per-ticket accuracy against it → *then* discuss automation. That's a project, not a next step.

---

### Q6.4 "What's the single next thing you'd do?"

**Short answer.** Get a Content specialist to read the 30 disagreement cases. Two hours, no cost, and it resolves the biggest open question in the deck.

**The full answer.** The 20.1% disagreement on the headline has three possible explanations — model error, agent error, matrix silence — and the deck can't distinguish them. Which one dominates changes the recommendations completely:

- Mostly model error → fix prompts, re-measure, and treat the findings as provisional.
- Mostly agent error → this becomes a training and code-hygiene issue, and the wastebasket use of "Others" is the target.
- Mostly matrix silence → the four policy recommendations are the whole story and should be actioned now.

Thirty tickets with both justifications side by side are already in `runs/output/csd_2026_validation_rules.xlsx`. Two hours of the right person's attention resolves it. Nothing else in the deck offers that ratio.

---

### Q6.5 "Does this apply to other Elsevier products?"

**Short answer.** The findings don't — they're specific to the Scopus content matrix. The method transfers directly, and has already been used on other corpora in this repository.

**The full answer.** Product-specific: every number here. The 24 rules, the 15 codes, the 17 discovered reasons, all volumes.

Transferable: the whole approach. Take a policy artefact, turn it into a classification taxonomy with an explicit "none applies", classify a stratified sample blind to the reference label, and cross-tabulate. Any product with a policy document and a resolution-code field can be measured this way.

Two prerequisites are worth checking before promising anything: the transcripts must be captured (10.9% weren't here), and the policy artefact must be structured enough to convert into a taxonomy. A prose guidelines document would need work first.

---

# 7 · Fast answers

Grab-bag for the questions that need one line, not a paragraph.

| Question | Answer |
|---|---|
| How many tickets in total? | 56,935 in the 2026 file; 50,714 classifiable; 12,000 sampled. |
| Why not 56,935? | 6,214 have no usable text. They're reported separately, never extrapolated over. |
| What's the headline? | 79.9% ± 0.6 — rule matches code, among tickets that could match. |
| What's the biggest gap? | Advice requests: 5,332 tickets a year, no rule can apply. |
| Cheapest fix? | Swap rule 08's primary and also-maps-to codes. 3,684 tickets a year. |
| How often does a ticket break two rules? | 2.3%. None break three. Rule 08 is in 68% of those that do. |
| How repeatable is the rule classifier? | 70.1% agreement across two independent passes over 12,000 tickets. |
| Is the model grading agents? | No. Nothing is cut by agent, team or individual. |
| Did the model see the resolution code? | No. Verified on the file header on disk. One ticket excluded for quoting its own code. |
| How much did it cost? | $242.52 rules and reasons; $416 effort; ~$660 total model spend. |
| Can I get per-ticket results? | Yes for the 12,000 — `runs/output/csd_2026_validation_rules.xlsx`. All 50,714 would cost ~$695. |
| Can I reproduce it? | Yes. Slide 63 lists every artefact and path. Seed 0, floor 300 per code. |
| Is 27.3% high-effort reliable? | To within a few points. Two runs gave 34.4% and 30.7%. Quote it as "a quarter to a third". |
| Best predictor of customer effort? | The model reading the transcript, +0.207. Handling metrics ≤ +0.112. |
| Do handoffs predict effort? | No. −0.028, indistinguishable from zero. |
| Are the 17 proposed rules ready? | No. Highest wording agreement is 17%. Evidence of a gap, not text to adopt. |
| What's the ceiling on the effort score? | +0.675 — its agreement with itself across two runs. |
| Who owns the fixes? | Content policy for recommendations 1–5; this analysis for 6–7. |

---

# 8 · Three questions to be careful with

These have no clean answer. Don't improvise — use these words.

### "Can you guarantee the model didn't see the resolution code anywhere?"

*"I can tell you what we verified, which is that the input file written to disk had exactly two columns, ticket ID and conversation text, and that we read that header back rather than trusting the code that produced it. We also excluded one ticket where the agent had pasted the code into the reply. What I can't rule out is a code appearing in transcript text in some paraphrased form we didn't pattern-match. We searched for the fifteen code strings; we didn't search for every possible rewording. My assessment is that the risk is small and would inflate conformance if it existed — but it's not zero, and I'd rather say that than overclaim."*

### "If we act on this and it turns out the model was wrong, who's accountable?"

*"The four policy recommendations don't depend on the model. Findings 1 and 2 are arithmetic on resolution codes and the matrix — 9,585 unclaimed tickets and the 59-versus-3,684 comparison would be true if we'd never run a classifier. Finding 3 depends on reading tickets but the conclusion is checkable by hand in an hour. What does depend on the model is the 79.9% conformance figure and everything in Part F. I'd act on the first group now and treat the second as directional until the 30 disagreement cases have been adjudicated."*

### "Why should we believe the effort findings when you're telling us the effort score is unreliable?"

*"Because unreliable and useless aren't the same thing. The score is noisy on any individual ticket and worth a few points of slack on any aggregate — I'd rather tell you that than have you find it later. But every conclusion in Part F is a ranking, not a point estimate. Content Format Issues at 60% high-effort against Duplicate Requests at 0.6% is a sixty-point gap; a few points of noise doesn't reorder it. And the alternative isn't a better measure, it's no measure — the handling metrics correlate worse with what customers actually said, and the survey only covers one ticket in twenty."*

<!-- slide numbers renumbered for the 63-slide deck -->
