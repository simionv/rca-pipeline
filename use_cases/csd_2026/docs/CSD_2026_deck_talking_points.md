# Talking points — *Why Scopus content requests are rejected*

Companion to `runs/output/CSD_2026_validation_rules_analysis.pptx` (60 slides).

**How to use this.** Each slide has up to four blocks:

- **On screen** — what the audience is looking at, so you can orient without turning round.
- **Say** — the spoken line. Written to be read aloud almost verbatim; trim, don't expand.
- **Concept** — the idea behind the slide, explained from first principles. Present only where a new idea is introduced.
- **Watch for** — the objection, misreading or trap this slide invites.

**Timing.** Roughly 35 minutes at a steady pace for slides 1–55, plus questions. The appendix (56–63) is reference material — do not walk through it. If you have 15 minutes, present 1, 2, 5, 9, 10, 21, 23, 34, 35, 42, 53, 54.

---

## Three errata to know before you present

**1. Slide 35's title says "65× rarer". The correct figure is 62×.** The table on that same slide shows 59 and 3,684, and 3,684 ÷ 59 = 62.4. The "65" is a leftover from an earlier population count that was not refreshed. Say **"more than sixty times rarer"** out loud. If someone does the division and challenges you, agree immediately: "You're right, it's 62 — the title is stale, the table is correct."

**2. Slide 45's last line reads "compared on slide x".** A placeholder that was never filled in. The answer is **slide 52**. Don't read that sentence off the slide.

**3. Slides 8, 40 and 62 say "Invalid- Others carries 4,125 tickets". The correct figures are 3,904 in the 2026 file, of which 2,729 are classifiable.** Slide 14's own table shows 3,904, so the deck contradicts itself. Another stale figure from an earlier population count. Say **"nearly four thousand tickets a year"**, and if challenged, point at slide 14.

All three are cosmetic and none touches a result. If you have time before the meeting, they are three string edits in `scripts/build_deck.py` followed by a rebuild.

---

## The five numbers to have by heart

| Number | What it is |
|---|---|
| **50,714** | Classifiable 2026 tickets. Every population figure projects to this, never to 56,935. |
| **79.9%** | The headline: how often the rule the ticket shows matches the code the agent logged, among tickets that could match. ±0.6pp. |
| **9,585** | Tickets a year whose resolution code no validation rule claims. An exact count, not an estimate. |
| **77.4%** | Matrix code coverage. Bounds the *strict* rate, **not** the headline. |
| **+0.675** | How well the effort score agrees with itself across two runs. The ceiling on everything in Part F. |

---

# Part 0 · Opening (slides 1–3)

### Slide 1 — Title

**On screen.** Title, subtitle, and the line "12,000 tickets classified · extrapolated to 50,714 classifiable 2026 tickets".

**Say.** "This is about the 2026 Content Service Desk corpus — every content request that was rejected. There are three separate things in the organisation that describe why a request gets rejected: a policy matrix, a set of resolution codes agents pick from, and whatever the agent actually wrote back to the customer. Until now nobody had put all three on the same ticket at the same time. That's what this did, on twelve thousand tickets, projected properly to the full year."

**Concept — why "extrapolated" and not "scaled".** The twelve thousand were not drawn evenly. Rare resolution codes were deliberately over-sampled so they could be measured at all. That means the sample does not look like the population, and you cannot simply multiply. Every projection here undoes the over-sampling mathematically. Slides 16–18 show how.

**Watch for.** Someone hearing "12,000 out of 57,000" and assuming a 21% sample of everything. It isn't — it's a 24% sample of the 50,714 that are classifiable, and within that it's stratified.

---

### Slide 2 — Executive summary

**On screen.** Five numbered findings, ordered by ticket volume affected.

**Say.** "Five findings. The first four are about the triangulation matrix — where it has holes, and how big they are in tickets per year. The fifth is the measurement itself.

One: three resolution codes are in daily use and no rule in the matrix claims any of them. That's 9,585 tickets a year with no policy behind the label.

Two: rule 08 is designated to produce 'Out of coverage'. That code appears 59 times in the year. The code rule-08 tickets actually carry is 'discontinued title', 3,684 times. Measured strictly, rule 08 conforms 2% of the time; measured against what it really produces, 85%. The rule isn't broken. The mapping is inverted.

Three: 1,534 tickets are logged as Articles in Press, and the two AiP rules in the matrix are both narrow special cases. A customer who simply says 'my article is in press and isn't in Scopus' fits neither.

Four: we drafted 17 candidate rules for the uncovered tickets, covering an estimated 7,696 a year. They're drafts for Content to review, not proposals to adopt.

Five: where a rule and a code can be compared, they agree 79.9% of the time, plus or minus 0.6."

**Watch for.** Being asked "so is 79.9% good?" — there is no benchmark, and you should say so. It is a baseline. Its value is that findings 1 to 4 explain most of the missing 20%, which makes the number actionable rather than merely disappointing.

---

### Slide 3 — What this analysis did

**On screen.** A four-row table of inputs, and a one-line statement of the output.

**Say.** "Four inputs. The Triangulation Matrix is the policy — 24 rules saying when a request is invalid. The ticket metadata carries the resolution code the agent logged, which is the only pre-existing label and therefore the reference. The CheatSheet gives the wording agents paste into replies, which we used as recognition cues so the classifier knows what rule 05 *sounds like* in practice. And the conversations themselves — 56,935 threads — are the evidence.

The output is that every ticket now carries all three labels at once, so for the first time they can be cross-tabulated."

**Concept — why the CheatSheet matters.** A rule written as policy ("published less than 4 weeks ago") looks nothing like what an agent types ("please allow up to 6 weeks for indexing"). Feeding the template wording into the rule descriptions is what lets the classifier recognise a rule from the reply rather than from the policy abstraction.

---

# Part A · Concepts and definitions (slides 4–10)

> This part exists because three of the four terms sound interchangeable and are not. Do not skip it — almost every hostile question in the Q&A pack is a definition question in disguise.

### Slide 4 — Part divider

**Say.** "Four terms carry the whole analysis, and three of them sound like synonyms. Two minutes on definitions saves twenty minutes of argument later."

---

### Slide 5 — The three artefacts, and why they disagree

**On screen.** A comparison table: validation rule vs rejection reason vs resolution code, across five dimensions.

**Say.** "Read the first row and the rest follows.

The **validation rule** answers: which policy makes this request invalid? It comes from the matrix, top-down, and there are 24 of them plus a 'none applies'.

The **rejection reason** answers: what ground did the agent actually give? It was discovered from the tickets themselves, bottom-up — nobody wrote it in advance. 17 categories in 5 groups.

The **resolution code** answers: what did the agent log in OSVC when they closed it? 15 values, all beginning 'Invalid-'.

The rule is the policy. The reason is what was said. The code is what was recorded. They line up where the matrix is complete and come apart where it isn't — and that coming apart is finding 1."

**Concept — why three views instead of two.** With only rules and codes, any disagreement is ambiguous: you cannot tell whether the model misread the ticket or the matrix has no answer. The rejection reason is the tiebreaker, because it was derived without reference to the matrix. When a reason is common and has no rule, the hole is in the policy, not the model.

**Watch for.** "Isn't the rejection reason just the resolution code renamed?" No — and slide 32 quantifies it. Their association is 0.45 on a 0-to-1 scale. If the reason were a restatement of the code it would be near 1.

---

### Slide 6 — Definition · Validation rule

**On screen.** Four blocks: plain English, in this analysis, the 'none applies' code, what was withheld.

**Say.** "A validation rule is a statement of when a request of a given type isn't valid. For instance: published less than four weeks ago, so too recent to be indexed yet.

Each rule became one leaf of a classification taxonomy. Its description carries the rule text, the CCG or CAR guideline reference, the wording an agent would use replying under it, and the analyst's mapping notes.

Two design points matter. First, CSDVR4.1 — 'no rule applies'. Without an explicit way to decline, a language model will force every ticket into *some* rule and the gaps in the matrix become invisible. That is exactly what happened on our first pass. Second, the rule's expected resolution code was never shown to the model. Agreement between rule and code is the quantity being measured; showing the model the answer would make the measurement circular."

**Concept — the escape hatch.** This is the single most important design decision in the deck. A classifier with no "none of these" option has a 100% coverage rate by construction and tells you nothing. Adding CSDVR4.1 is what converts the exercise from "label every ticket" into "find out what the matrix can't label" — and 15.2% of tickets took it.

**Watch for.** "How do you know the model isn't over-using the escape hatch?" Answer: because the tickets that take it concentrate in three specific resolution codes (slide 34), not spread uniformly. Random over-use would not produce that pattern.

---

### Slide 7 — Definition · Rejection reason

**On screen.** Four blocks: plain English, why it isn't the rule, how it was built, why bottom-up.

**Say.** "The rejection reason is the substantive ground the agent gave, in the agent's terms rather than the policy's.

It was built in two passes over a stratified sample of 353 tickets. The first pass extracted one abstract reason per ticket in free text. The second normalised those into a two-level taxonomy — 5 groups, 17 leaves. Two categories were added by hand because the corpus needs them and a bottom-up pass won't invent them: 'status enquiry only', and 'no reason stated'.

It is bottom-up on purpose. It's the only view in the analysis not derived from the matrix, so it's the only one that can show what the matrix is missing."

**Concept — discovery versus classification.** Discovery reads a small sample and asks "what categories exist here?" Classification reads a large sample and asks "which of these known categories applies?" Doing them in that order means the taxonomy is shaped by the corpus rather than by the analyst's expectations. The cost was $3.

**Watch for.** "Why only 353 tickets for discovery?" Because discovery is about finding the categories, not counting them. Categories saturate quickly — by 353 tickets new reasons had stopped appearing. The counting happened afterwards, on all 12,000.

---

### Slide 8 — Definition · Resolution code

**On screen.** Four blocks, ending on "Consequence for reading this deck".

**Say.** "The resolution code is what the handling agent selected when closing the ticket. All 15 values in this corpus start 'Invalid-', so every ticket in scope is a rejected request.

It's the reference standard for one reason only: it already exists on all 56,935 tickets and it was produced independently of this analysis.

It is not truth. It's one agent's choice under time pressure. 'Invalid- Others' carries thousands of tickets and functions as a wastebasket. Where the model and the agent disagree, either can be wrong.

So — and this is the consequence for reading everything after this slide — conformance measures agreement with the matrix. It is not an accuracy score and it should never be quoted as one."

**Watch for.** This is the slide that protects you for the rest of the session. If anyone later says "so the model is 79.9% accurate", point back here. Being explicit about the weakness of your own reference standard is what makes the rest defensible.

---

### Slide 9 — Definition · Conformance

**On screen.** A table of three rates, each with its denominator, its value, and its maximum. Below it, the identity 81.1% × 79.9% = 64.8%.

**Say.** "Three conformance rates, and the difference between them is entirely the denominator.

**Strict**, over all rule-tagged tickets: does the logged code equal the rule's designated primary code? 64.8%. Its maximum is not 100% — it's 81.1% — because a ticket whose code no rule claims can never conform no matter how well the classifier performs.

**Loose** additionally counts the matrix's own 'also maps to' codes. 71.5%. Same ceiling.

**Conformance among mappable** — the headline — restricts to tickets that *could* conform, and asks how often they do. 79.9%. Its maximum is 100%.

And they're consistent: 81.1% times 79.9% is 64.8%. Strict equals the mappable share times the headline. If those three numbers didn't multiply out, one of them would be wrong."

**Concept — why three numbers instead of one.** The strict rate mixes two different failures: the matrix having no answer, and the answer being wrong. Splitting them separates a policy problem (fix the matrix) from a measurement problem (fix the classifier, or accept the disagreement). The headline isolates the second; matrix code coverage on the next slide isolates the first.

**Watch for.** Someone asking which number is "the real one". All three are real; they answer different questions. Use the headline when discussing classification quality, strict when discussing end-to-end policy coverage. Never quote one without its denominator.

---

### Slide 10 — Definition · Matrix code coverage

**On screen.** 77.4%, then three blocks: what it bounds, what it does not bound, why it matters.

**Say.** "77.4% of tickets carry a resolution code that some rule claims as its primary. That is a property of the matrix, not of this analysis — it would be the same number if we'd never classified anything.

It bounds the strict rate, for the reason on the previous slide.

It does **not** bound the headline. The headline is already restricted to tickets that can conform.

I'm labouring this because the two numbers sit at 77.4% and 79.9%, and read side by side they invite the conclusion that we've hit a ceiling and there's nothing left to gain. That's wrong. The headroom on the headline is 20.1 points."

**Watch for.** This slide exists because that exact misreading happened during the analysis. Expect it in the room. The rebuttal is one sentence: *different denominators — one counts tickets the matrix can't reach, the other counts tickets it reached and got wrong.*

---

# Part B · Method (slides 11–19)

> Present this in full to an analytics or data-governance audience. For a policy audience, cover 13, 15 and 16 and offer the rest on request.

### Slide 11 — Part divider

**Say.** "How the tickets were classified, how the sample was drawn, and how it projects to the year. If you only take one thing from this section, take slide 18 — why a single multiplier would have been wrong."

---

### Slide 12 — The pipeline

**On screen.** Four stages with scale and cost. Total $242.52.

**Say.** "Four stages. Build turns the matrix into a classification taxonomy and generates prompts — those prompts were checked verbatim against the source, free. Discover reads 353 tickets to induce the rejection-reason taxonomy, $3. Tag runs all 12,000 tickets through both classifiers, each answer carrying a justification and a verbatim quote from the transcript, $164. Analyse is the cross-tabulation and extrapolation, free.

Everything including the gates and three rounds of prompt iteration came to $242.52. Classifying all 50,714 rather than sampling would have been about $695."

**Watch for.** The cost is low enough to invite "just run everything then". Slide 43 has the answer: at ±0.6 points a full run buys precision nobody would use. It's worth doing only if you need a tag on every individual ticket for operational use.

---

### Slide 13 — From corpus to classified sample

**On screen.** A funnel chart, plus the exclusion breakdown.

**Say.** "56,935 tickets in the 2026 file. 6,214 can't be classified: 5,844 are chat threads whose transcript was never captured, 369 have under 300 characters of text, and one quoted its own resolution code in the transcript, which would have leaked the answer. That leaves 50,714 classifiable, and 12,000 of those were sampled.

The excluded tickets are reported separately and never extrapolated over. Nothing in this deck claims anything about them."

**Concept — the 300-character floor.** Below roughly 300 characters there isn't enough text for any reader, human or model, to identify a rejection ground. Including them would manufacture labels out of noise. Excluding them is honest but it isn't free — the next slide is about the price.

---

### Slide 14 — The exclusions are not random

**On screen.** Exclusion rate by resolution code, worst first: advice request 33.9%, Others 30.1%, down to Not-Missing 3.7%.

**Say.** "This is the slide I'd want a critic to check. The exclusions are not random. A third of advice-request tickets are unclassifiable, against under 4% of Not-Missing ones — nine times the rate.

That's why we never project onto the full 56,935. Assuming the excluded tickets behave like the classified ones would overstate the rule-covered share, because the tickets most likely to be excluded are exactly the ones least likely to have a rule."

**Concept — non-random missingness.** When what's missing is missing *for a reason related to what you're measuring*, dropping it biases the result in a knowable direction. Here the direction is knowable and adverse: advice requests are both the most-excluded group and the group with no rule. So findings 1 and 2 — the gaps — are if anything **understated**. That is the right way round for a governance finding: the known bias runs against the conclusion, not towards it.

**Watch for.** Say the direction out loud. "Our known bias makes the gap look smaller than it is" is a much stronger position than "we have a bias".

---

### Slide 15 — How the sample was drawn

**On screen.** Sample-versus-population bar chart, plus the rationale for the floor.

**Say.** "Stratified by resolution code with a floor of 300 tickets per code. Deliberately not proportional.

Here's why. 'Invalid- Out of coverage' has 59 tickets in the entire year. A proportional sample of 12,000 would contain 14 of them and we could say nothing about that code — which happens to be rule 08's designated code, so we'd have missed finding 2 entirely.

The floor guarantees every code is estimable. Two codes were rarer than the floor, so the sample took all of them: Out of coverage, and Not within scope. Those two are a census. Their figures carry no sampling error at all."

**Concept — why over-sample the rare.** Precision on a rate depends on the count *within* the group, not on the overall sample size. 14 tickets gives you an interval of roughly ±25 points — useless. 59 gives you certainty, because it's all of them. The price is that the sample no longer resembles the population, which is what the weights on slide 16 pay back.

---

### Slide 16 — Extrapolating to the full year

**On screen.** The estimator: weights, p̂ = Σ Wₕ·pₕ, and the variance with finite-population correction.

**Say.** "Each sampled ticket stands for w = N over n tickets in its own stratum — the population count for that code divided by how many we sampled. Weights run from 1.00, a census, to 5.27. They sum to exactly 50,714, and that's an arithmetic check we run every time.

The estimate is the rate inside each stratum, weighted by that stratum's true share of the population.

The interval has a finite-population correction — the last term, one minus n over N. When a stratum is sampled in full that term goes to zero: we measured that stratum, we didn't estimate it, so it contributes no uncertainty.

Every population figure in Part C carries the resulting 95% interval. They're typically half a point, because 12,000 against 50,714 is a large sample and the correction is doing real work."

**Concept — what the interval means.** ±0.6 points on the headline means: if you re-drew the sample the same way many times, 95% of those samples would put the true population rate inside 79.3% to 80.5%. It covers *sampling* error only. It does not cover the model being wrong, the agent being wrong, or the excluded tickets. Say that if the interval is quoted back at you as if it were a total error bar.

---

### Slide 17 — What each sampled ticket stands for

**On screen.** Design weights by code. Two orange bars at 1.00.

**Say.** "A 'premature' ticket in the sample speaks for 5.27 tickets in the year, because that code is huge and was deliberately under-sampled relative to its size. The two orange bars are the census strata — weight exactly 1.00, nothing to project, no sampling error.

The bars sum to 50,714 exactly."

---

### Slide 18 — Why a single multiplier would be wrong

**On screen.** Naive-versus-correct error per code, with the Non-GenCAR worked example.

**Say.** "This is the slide that justifies the whole method.

If you took the sample and multiplied by 4.227 — twelve thousand into fifty thousand seven hundred — here's what happens to 'Invalid- Non-GenCAR'. There are 307 in the population. We sampled 301 of them, nearly all. Naive scaling gives 301 times 4.227, which is 1,272 tickets — four times more than exist. The correct weight is 307 over 301, essentially one, and you get 307.

The same logic runs the other way on 'premature', the largest code, and understates it by 20%.

Across individual rules and reasons the naive error runs from minus 20% to plus 50%. That's why nothing in this deck is a multiplied sample."

**Watch for.** Somebody may have circulated a flat-multiplied number in a previous conversation. This is the slide that gently retires it. Don't name anyone; just show the arithmetic.

---

### Slide 19 — How the classification was validated

**On screen.** Five controls and what each caught.

**Say.** "Five controls before the main run.

**Blindness.** The resolution code never reaches the model. The input file has two columns, ticket id and conversation; we verified the header as written on disk, not as intended; and one ticket was excluded for quoting its own code in the text.

**A 40-ticket smoke test.** Every answer must be a valid code, and the verbatim evidence quote must actually appear in the transcript for at least 80% of tickets. That catches a model that's inventing quotes.

**Three probe rounds of 1,000 tickets.** These caught real defects and fixed them: rule 05 recall went from 49% to 89%; rule 07 precision from 37% to 73%; discontinued-title routing from 23 out of 70 correct to 56 out of 70.

**A boilerplate audit.** Agents close most coverage replies with 'any journal may be subject to re-evaluation at any point'. The model was reading that standing disclaimer as a positive finding on 44% of such tickets. Naming it as insufficient evidence cut that to 24%.

**Confidence intervals on the audits themselves** — Wilson lower bounds — so a two-point movement on an 88-ticket stratum isn't mistaken for a real improvement. That's why tuning stopped when it did."

**Concept — why blindness matters more than it sounds.** If the model can see the resolution code, it will infer the rule from the code, and conformance becomes a measure of the model's ability to read a lookup table. The measurement would come out near 100% and mean nothing. Everything in Part C depends on this having been done properly, which is why it was verified against the file on disk rather than against the code that wrote it.

**Watch for.** "Did you tune the prompt until you liked the number?" Honest answer: we tuned it three times, the headline moved from 67% to the 75–79% range, and we stopped when the change between rounds fell inside the sampling interval of the probe. Slide 61 has the full record — that transparency is the defence, not a denial.

---

# Part C · Results (slides 20–32)

### Slide 20 — Part divider

**Say.** "Sample beside population estimate throughout. Where they differ, the difference is the stratification being undone — it isn't noise, it's the correction."

---

### Slide 21 — Coverage

**On screen.** Four rows: tickets classified, rule applies, no applicable rule, no reason stated — sample and population side by side.

**Say.** "12,000 classified, standing for 50,714.

A validation rule applies to 84.9% of the sample, 84.8% of the population — 43,018 tickets a year.

No rule applies to 15.2%, which is 7,696 tickets a year, plus or minus 255. That is the size of the hole, and it's the number recommendation 5 is scoped against.

And 3.6% of tickets — 1,823 a year — state no reason at all. The agent closed them without giving a ground.

One convention for the rest of the deck: a figure defined by a resolution code is an exact 2026 count. A figure defined by our classification is a design-weighted estimate and carries a ± interval. If you see a ±, we inferred it; if you don't, we counted it."

**Watch for.** "1,823 tickets with no stated reason — is that a service quality problem?" Fair question, and it's outside this analysis. It may be legitimate (a one-line answer to a one-line question) or not. Flag it as worth a separate look rather than speculating.

---

### Slide 22 — Headline rates (chart)

**On screen.** Sample versus population bars for the headline rates.

**Say.** "Loose conformance falls 3.2 points when you weight it, because the codes it rescues — discontinued title above all — were over-sampled. The headline rises 1.0 point.

Neither shift is large. But neither is zero, and that's the entire argument for weighting rather than assuming the sample is representative."

---

### Slide 23 — Headline rates in full

**On screen.** Seven rates with denominator, sample, population and shift.

**Say.** "Every rate with its denominator, because a conformance number without a denominator is meaningless.

The headline: 79.9%, plus 1.0 point against the raw sample. Strict: 64.8%, down 2.2. Loose: 71.5%, down 3.2. Rule applies: 84.8%, essentially unchanged. And the mappable share, 81.1%, down 3.8 points — the largest shift on the slide, and the reason strict and loose moved."

**Watch for.** The mappable share carries ±0.0%. That is correct, not a rounding error: whether a code is claimed by some rule is a property of the matrix, so once you know each ticket's code the mappable share is a weighted count, not an estimate. There is no sampling uncertainty in it.

---

### Slide 24 — Validation rules by volume (chart)

**On screen.** Sample share versus estimated population share per rule.

**Say.** "The bars are sample share against population share. Where they diverge, that rule is concentrated in an over- or under-sampled code. Rule 05 — too recent — is the largest at 11,529 tickets a year. Rule 06, already in Scopus, is next at 8,788. And the third bar is 'no applicable rule' at 7,696 — the third most common outcome in the entire year is the matrix having nothing to say."

**Watch for.** Land that last sentence. It's the most quotable line in Part C.

---

### Slide 25 — Validation rules — the numbers

**On screen.** Top 10 rules with sample n, population estimate, and naive error.

**Say.** "The right-hand column is what a flat multiplier would have got wrong. Rule 03, unauthentic publisher site: naive scaling overstates it by 38%. Rule 14, MEDLINE AiP: by 40%. Rule 06 understates by 18%. These aren't rounding differences — a flat multiplier would have put rule 03 at nearly 2,700 tickets a year when it's 1,923."

---

### Slide 26 — Rejection reasons by volume (chart)

**Say.** "Same treatment, bottom-up categories. 'Content Not Yet Indexed' dominates at 16,575 tickets a year — a third of everything. That's a single message repeated sixteen thousand times: it's too soon, please wait."

**Watch for.** This is where a service-improvement audience will start thinking about deflection. Let them, but don't promise anything — deflection potential is not measured here.

---

### Slide 27 — Rejection reasons — the numbers

**On screen.** Top 10 reasons with naive error.

**Say.** "Note 'Ineligible Content Types': naive scaling overstates it by 50%, the largest error on the slide. And 'Content Already Indexed' understates by 17%. Same lesson as slide 25 — the weighting is not a formality."

---

### Slide 28 — Validation rule × resolution code (heatmap)

**On screen.** Row-normalised, weighted heatmap.

**Say.** "Read this row by row: given the rule, which code did the agent log? A perfect matrix would be a bright diagonal. The bright cells off the diagonal are where the matrix's expectation and the agents' practice have separated, and the brightest of those is rule 08's row — which is finding 2."

**Concept — row-normalised.** Each row sums to 100%, so the colour is a conditional probability, not a volume. A bright cell in a rare rule's row can be a handful of tickets. Always read the heatmap alongside the volume tables on slides 25 and 49.

---

### Slide 29 — Rejection reason × validation rule (heatmap)

**Say.** "Given the reason the agent gave, which rule did the classifier assign? The 'no applicable rule' column is the one to look at: where a reason routes heavily into that column, the matrix has no policy for a ground agents are actually giving."

---

### Slide 30 — Rejection reason × resolution code (heatmap)

**On screen.** The third heatmap, same treatment as 28 and 29: design-weighted, row-normalised.

**Say.** "The third face of the same cube, and the only one where neither axis depends on the matrix — the reason came from the tickets, the code came from the agent.

Read the bright cells. Duplicate Requests go to 'Not Missing' 96% of the time. Content Already Indexed, 90%. Status Inquiries, 88%. Content Not Yet Indexed goes to 'premature' 68%. Where a reason has an obvious code, agents find it.

Now look at Source Coverage Issues — it splits, 43% to 'discontinued title' and 32% to 'advice request'. Both of those are codes no rule claims. So the reason that most often lands on an unmapped code is the same one the next two slides are about."

**Concept — why this pairing matters most.** Rule × code tests the matrix against practice. Reason × rule tests the matrix against what agents say. This one tests two independent descriptions of the ticket against each other, with the matrix removed from both axes. Where it is clean, the corpus is genuinely well structured; where it smears, the ambiguity is real rather than an artefact of the policy document.

---

### Slide 31 — The three-way relationship

**On screen.** Eleven combinations of reason × rule × code, with a "conforms" column.

**Say.** "642 populated cells; these 11 account for 57.5% of the year, so the corpus is far more concentrated than its 24 rules and 15 codes suggest.

Two rows are worth stopping on. Row four: Source Coverage Issues, rule 08, discontinued title — 2,879 tickets a year, marked *no*. That's finding 2, in the form it takes on real tickets.

Rows seven and eight: Source Coverage and Journal Re-evaluation, no applicable rule, advice request — 2,545 tickets a year between them, also *no*. Those are enquiries, and no rule in the matrix is written about an enquiry."

---

### Slide 32 — How strongly the three axes are related

**On screen.** Bias-corrected Cramér's V for the three pairs.

**Say.** "Cramér's V measures association between two categorical variables: 0 is independence, 1 is a perfect relationship. Bias-corrected, because with 23 by 15 categories the raw statistic is inflated by chance alone.

Rule and code are the strongest pair at 0.62, which is exactly as it should be — the matrix asserts that link, and this confirms it holds.

Reason and code sit lower at 0.45. That's the useful number: the discovered reasons are *not* a restatement of the codes. If they were, they'd be near 1 and they'd tell us nothing new.

All three are far from independence, so the matrix is describing something real. The question is only where it's incomplete."

**Watch for.** "Is 0.62 good?" There's no threshold. Its meaning here is relative: rule–code is stronger than reason–code, which is the ordering you'd predict if the matrix is a genuine but partial description of practice. Had reason–code come out higher than rule–code, the matrix would be a worse description of practice than a taxonomy induced from scratch — and *that* would have been the headline.

---

# Part D · Findings (slides 33–40)

### Slide 33 — Part divider

**Say.** "What the classification revealed about the matrix itself. Everything from here is about the artefact, not about the tickets."

---

### Slide 34 — Finding 1 · Three resolution codes no rule claims

**On screen.** Chart of the three unmapped codes; 9,585 total.

**Say.** "Three codes are in daily use and no rule in the matrix claims any of them as its primary. 9,585 classifiable tickets a year. This is an exact count, not an estimate — it's defined entirely by the resolution code, which we know for every ticket.

**Advice request, 5,332.** These are status enquiries. Every rule in the matrix is phrased about a *request* — a request to add, to correct, to change. An enquiry has no request to invalidate, so no rule can fit by construction.

**Discontinued title, 3,684.** It appears in the matrix only as an 'also maps to' on rule 08. That's finding 2.

**Book, 569.** Book and conference coverage sits outside the matrix's two request types entirely.

And the matrix already knows. The workbook carries a sheet named 'Unmapped invalid res codes'. This finding quantifies something its authors had already flagged."

**Watch for.** That last point disarms the defensive reaction. You are not telling Content something they got wrong; you are putting a number on something they had already noted and could not size.

---

### Slide 35 — Finding 2 · Rule 08's designated code

> **Erratum: the title says 65×; the correct figure is 62×.** Say "more than sixty times".

**On screen.** Two-column comparison: designated code vs actual code.

**Say.** "The matrix designates 'Out of coverage' as rule 08's primary resolution code. In the whole of 2026 that code appears on 59 classifiable tickets.

The code rule-08 tickets actually carry is 'discontinued title' — 3,684 of them, more than sixty times as many. And in the matrix that code is only an 'also maps to'.

Measured strictly, rule 08 conforms 2.2% of the time. Measured against the code it really produces, 84.7%.

Rule 08 is not performing badly. It is being measured against a code that is almost never used. The primary and the also-maps-to are the wrong way round.

The fix is one of two things: swap them, or promote 'discontinued title' to a primary code of its own. Either change moves roughly 3,500 tickets a year from non-conforming to conforming without touching a single ticket or retraining a single agent."

**Watch for.** This is the strongest recommendation in the deck: highest volume, lowest cost, no operational change. If the meeting only produces one decision, aim it at this one. The likely objection — "so you're just redefining the target to make the number better" — deserves a direct answer: the strict rate stays in the deck, both are reported, and the argument for the swap is that 3,684 agents' decisions are better evidence of practice than one cell in a mapping table.

---

### Slide 36 — Deep dive · Invalid- discontinued title

**On screen.** A six-row table: matrix status, what the classifier reads, what the agent said, conformance, customer effort, what the fix buys.

**Say.** "The single largest unmapped code that is an actual request rather than an enquiry — 3,684 classifiable tickets.

Every line on this slide points the same way. In the matrix it exists only as an 'also maps to' on rule 08, so mappability is zero and strict conformance can never be anything but zero. The classifier reads 82% of these tickets as rule 08. The agents' own stated reason is 'Source Coverage Issues' on 89%. Strict conformance 0%, loose 82%.

And it is the highest-effort resolution code we measure: 69% judged high effort, and 30% of the customers who answered the survey said it was not easy.

So: one code, one rule, one reason, and the worst customer experience in the corpus — and the entire gap is a mapping table with the primary and the also-maps-to the wrong way round."

**Watch for.** Someone will ask why this needs its own slide when Finding 2 already covers rule 08. The answer is that Finding 2 argues from the rule's side and this argues from the code's side, and they meet in the middle. If the room is going to authorise one change, this is the slide that makes it feel small: one cell, no ticket touched, no agent retrained.

**Note.** There is deliberately no year-on-year row. The 2025 comparison figure is a full calendar year and this corpus is not, so stating it in the deck's own framing would read as a 46% collapse that is purely the period mismatch.

---

### Slide 37 — How often is a ticket failed by more than one rule?

**On screen.** A five-row table and a bar chart of rules per ticket, with a red caveat block.

**Say.** "A fair question about any single-label classifier: what if a ticket breaks two rules and we only recorded one? So we ran a separate pass over the same twelve thousand tickets, asking which rules apply rather than which fits best.

97.7% of tickets break exactly one rule. 2.3% break two. Nothing anywhere in the run broke three.

The interesting part is where the overlap sits. Rule 08 is in 68% of every multi-rule ticket — it pairs with rules 01, 02, 03, 05 and 06. Its condition, pre-dates coverage start or falls after the last covered year, can be true alongside almost anything. That is a third independent line of evidence pointing at the same rule as Finding 2 and the deep dive.

Two caveats, and I would rather give them than be asked. This is a lower bound: eight of the twenty-five rule descriptions carry single-label wording — 'not this rule', 'do not use' — that we added during the original tuning, so the taxonomy discourages double-labelling. And the second pass agreed with the original run on 70% of tickets, which means the classifier disagrees with itself about ten times more often than tickets break two rules."

**Concept — why the 70% is on this slide at all.** The second pass is an independent read of the same taxonomy, so comparing its best-fit answer to the original gives the rule classifier's test–retest agreement — a number we previously did not have and said so. It is the most important thing on the slide, and it is not flattering: 30% disagreement bounds how precisely any per-rule figure in this deck should be read.

**Watch for.** "So the 2.3% is meaningless if the classifier is only 70% repeatable?" No, but be precise. The multi-rule rate is an aggregate over 12,000 tickets, and aggregates are far more stable than individual labels. What the 70% bounds is confidence in any *single* ticket's rule, and the precision of the smaller per-rule conformance figures in the appendix.

---

### Slide 38 — Finding 3 · Articles in Press

**On screen.** Three rows: rule 14, rule 22, and a dash for the general case.

**Say.** "1,534 tickets a year carry the AiP resolution code. The matrix has two AiP rules and both are narrow. Rule 14 is about MEDLINE-sourced titles and unapproved publishers — a sourcing case. Rule 22 is about missing volume, issue or page on an AiP — a correction case.

A customer who says 'my article is in press and isn't in Scopus yet' fits neither.

The classifier routes those to rule 05, too recent, which is a defensible reading of the transcript but not what the agent logged. And I want to be explicit: we could add a prompt cue to force them into the MEDLINE rule and the conformance number would improve. We deliberately didn't, because it would make the crosstab wrong in a way that looks right.

This is a matrix gap, not a model defect. It needs a general AiP rule."

**Watch for.** This slide is where you establish that the analysis isn't optimising its own score. Say the "we could have tuned this and chose not to" line — it buys credibility for every other number.

---

### Slide 39 — Finding 4 · Candidate rules drafted for the gaps

**On screen.** Six of the 17 drafts, with observed code, estimated volume, and model agreement.

**Say.** "For the tickets no rule covered, we asked the model to draft what the missing rule would say, in the matrix's own phrasing. 17 candidates, covering an estimated 7,696 tickets a year.

The column to read is the last one. 'Model agreement' is how consistently the same wording came back across tickets of the same kind. The top candidate — guarantees about future indexing — is 9%. Every candidate is below 10%, and the highest across all 16 distinct drafts is 17%.

So: the *gap* is well evidenced, because it's defined by tickets no rule covered. The *wording* is not. Treat these as evidence that a rule is needed and as a starting draft — not as text to adopt."

**Watch for.** Do not let anyone leave thinking these are ready to paste into the matrix. If somebody asks for them as a deliverable, point at `runs/output/csd_2026_rule_proposals.xlsx` and repeat the 17% ceiling.

---

### Slide 40 — Finding 5 · Where the classifier and the agents disagree

**On screen.** Disagreement chart.

**Say.** "When the rule and the code disagree, there are always exactly three explanations and this analysis cannot distinguish them.

One: the model misread the ticket. Two: the agent picked the wrong code — remember 'Invalid- Others' carries nearly four thousand tickets a year and acts as a wastebasket. Three: the matrix has no right answer, so both parties improvised.

Thirty disagreement cases, with both the model's justification and the logged code, are in the deliverable workbook. Someone from Content reading those thirty would tell us which of the three dominates, and that's the cheapest next step in this whole deck."

**Watch for.** Make this an explicit ask. "Thirty tickets, maybe two hours of a Content specialist's time" is a concrete, small commitment and the highest-value thing anyone in the room can offer.

---

# Part E · Recommendations (slides 41–43)

### Slide 41 — Part divider

**Say.** "Ordered by the number of tickets each change affects in a year."

---

### Slide 42 — Recommendations

**On screen.** Seven actions with owner and annual volume.

**Say.** "Seven, and the first four are all Content policy.

One, swap rule 08's primary and also-maps-to, or give discontinued title its own primary code — 3,684 tickets. Cheapest, largest, no operational change.

Two, add a rule for status and coverage enquiries — 5,332 tickets. This is the biggest single gap and also the hardest, because it means deciding whether an enquiry can be 'invalid' at all, or whether it needs a different disposition altogether.

Three, a general Article-in-Press rule — 1,534. Four, a book and conference rule — 569.

Five, review the 17 drafted candidates, adopt, rewrite or reject each — 7,696 estimated. That's Content plus CSD.

Six is ours: sharpen the rule 15 versus rule 06 boundary. 45% of rule 15's errors land on one code, which is a prompt fix, not a policy fix.

Seven, also ours: re-run over all 50,721 tickets once the matrix is revised, if you want a per-ticket tag. $695."

**Watch for.** Recommendation 2 is the one that will generate discussion, because it isn't a mapping change — it's a question about what the matrix is *for*. Have the answer ready: the matrix validates requests, and 5,332 tickets a year aren't requests. That may need a new disposition type rather than a new rule.

---

### Slide 43 — What this cost, and what it would cost to complete

**On screen.** Cost table, $242.52 total, ~$695 for the full corpus.

**Say.** "Full accounting from the run's own token records. $3 discovery, $56 on validation gates — five smoke tests and three probe rounds — $164 on the main run, $8 on the gap pass. $242.52 all in.

The sample was the right call. At ±0.6 points on the headline, a full run buys precision nobody would use. It's worth doing only if the deliverable has to be a tag on every individual ticket — for instance if you want to route tickets by rule in production."

**Watch for.** "That's cheap, why not do everything?" The constraint is not money, it's that more precision on an already-precise number changes no decision. The full run has one genuine use — per-ticket operational tagging — and that's a different project with a different justification.

---

# Part F · Customer effort (slides 44–55)

> **Frame this section correctly from the start.** Parts A–E measure agreement between artefacts. Part F is the only part that touches how the customer felt, and only slide 53 has an actual customer in it. Slide 54 is the honesty slide and you should not skip it.

### Slide 44 — Part divider

**Say.** "What the interaction cost the customer, and how that lines up with the rules and reasons. This section has a weaker evidence base than everything before it, and I'll be explicit about where."

---

### Slide 45 — Two readings of the same interaction

> The slide's last line ends "compared on slide x". Say **slide 52**.

**On screen.** Observed effort vs judged effort across five dimensions.

**Say.** "Two independent readings.

**Observed effort** comes from the thread record — turns, distinct agents, timestamps. It's exact, there's no model in it, and it covers all 56,935 incidents. It's blind to *why* the customer was frustrated.

**Judged effort** is the model reading the transcript and returning an effort level, friction points, themes and a transparency judgement. It covers the 12,000 scored tickets. It's a judgement, though every one is grounded in a verbatim quote. It's blind to anything not written down.

They were computed independently and compared on slide 52. Agreement between them is corroboration, not validation — no customer has told us how hard any of these tickets were. Survey data is expected and the notebook is built to accept it."

**Concept — corroboration versus validation.** Two independent measurements agreeing raises confidence that they're measuring *something* real, but if both share a blind spot they'll agree and both be wrong. Only an external reference — the customer — validates. That distinction is why slide 53 is a different kind of slide from slide 52.

---

### Slide 46 — How observed effort is measured

**On screen.** Five signals with typical values.

**Say.** "From 176,083 thread entries across all 56,935 incidents. No model, no cost, fully reproducible.

Median thread is 3 turns. Mean 0.72 agent handoffs, with 57% of incidents having at least one. Median resolution span 76 hours. And 62% of tickets come from a customer who raised another ticket — with an important caveat: for about 13% we can't resolve the contact, and those are recorded as *unknown*, not as *no*. Coding unknown as false would have quietly understated repeat contact.

The composite index is an equal-weight mean of four percentile-ranked signals. It's authored, not fitted — there's nothing to fit against until the survey lands. Its components are published so it can be reweighted rather than rebuilt."

**Watch for.** "Why equal weights?" Because any other weighting would have been fitted to something, and the only thing available to fit to was the model's own judgement — which would make slide 52 circular. Equal weights are a declared assumption, not an oversight. Slide 53 shows what the assumption cost: the composite underperforms its own best component.

---

### Slide 47 — How much effort, overall

**On screen.** Five-level distribution, sample and population.

**Say.** "27.3% of tickets are judged high or very high effort — an estimated 13,829 a year.

The extremes are thin: very low is 1.2%, very high is 0.6%. Nearly everything lives in the low/medium/high band, and that's exactly where the incoming survey will matter most, because that's where the distinctions are hardest to trust."

**Watch for.** Read this against slide 54 before quoting 27.3% anywhere. The two runs of the same prompt put the sample rate at 34.4% and 30.7%. Quote effort rates as "roughly a quarter to a third", not to one decimal place.

---

### Slide 48 — Effort by rejection reason

**On screen.** Share judged high-effort per reason, with a dashed line at 27.3%.

**Say.** "This is the most actionable chart in Part F, because rejection reason is the axis a service owner can act on.

At the bottom, 'Duplicate Requests' at 0.6% and 'Status Inquiries' at 5.9% — the customer asks, gets an answer, done.

At the top, 'Content Format Issues' at 60%, 'Ineligible Content Types' at 53%, 'Source Coverage Issues' at 47%. These are the refusals that take work to deliver and work to absorb.

And note 'Content Not Yet Indexed' at 13% — the single largest reason in the corpus, 16,575 tickets a year, and it's *below* the line. High volume, low effort. That matters for prioritisation: the biggest bucket is not the painful one."

**Watch for.** The instinct in the room will be to attack the largest bar by volume. The point of this chart is that volume and pain point at different targets.

---

### Slide 49 — Effort by validation rule

**On screen.** Eleven estimable rules with % high-effort, mean score and median span.

**Say.** "Same cut by rule. The spread is wide — from 7.8% on rule 06 to 70% on rule 24.

Two patterns. The rules that say 'wait' — 05 too recent at 9.8%, 07 already in the pipeline at 8.9% — are low effort. The rules that say 'no, and here's a complication' — 08 coverage mismatch at 68.7%, 03 unauthentic publisher at 68.5% — are high effort.

And look at the median span column against the effort column. Rule 15 has the second-longest span at 140 hours but only 35.7% high effort. Long doesn't mean hard. That's the same lesson slide 53 makes quantitatively."

---

### Slide 50 — Where the friction is

**On screen.** Nine friction categories with volume and % high-effort when present.

**Say.** "Nine normalised friction categories. The eight standard ones, plus one we had to add.

By volume, 'slow response / long wait' leads at 28.7% of tickets. But the column that matters is the share judged high-effort when the friction is present. 'Repeated issue explanation' — 97%. 'Escalation required' — 87%. 'Redirected to another party' — 86%.

That last one is the added category. The eight standard categories had no home for being told to take your request somewhere else. On a corpus that is entirely rejections, that isn't an edge case — it's the outcome for a large minority, 6,126 tickets a year. Twelve per cent of tickets, and 86% of those are high effort."

**Concept — normalisation.** The model returns friction points in free text, so the same idea arrives as a dozen phrasings. Normalisation maps them onto a fixed vocabulary so the counts mean something. Worth knowing: this normalisation step existed in the codebase but had never actually been switched on — the category list was missing from the configuration, so it had been silently doing nothing on earlier runs. This is the first analysis where it ran.

**Watch for.** If anyone owns downstream effort reporting from earlier runs, that last point is relevant to them. Raise it as information, not as a fault.

---

### Slide 51 — Does the matrix failing a ticket cost the customer effort?

**On screen.** Four segments by conformance status, share high-effort.

**Say.** "This is the slide that connects Part D to Part F, and it's the one I'd put in front of a governance board.

Where the rule and the logged code agree — 30,428 tickets a year — 21.3% are high effort. That's the baseline.

Where they disagree — 6,484 tickets — 35.0%. Nearly 14 points worse.

Where no rule applies — 7,696 tickets — 23.4%. Only slightly worse.

And where the code is one no rule can claim — 9,585 tickets — 38.9%. Seventeen and a half points above baseline.

So the matrix's blind spots are not just a bookkeeping problem. They correlate with a measurably harder experience.

One caution, and I want to say it rather than have it asked: this is correlation. The likely mechanism is that hard, ambiguous cases are both harder to classify and harder to resolve — the matrix gap doesn't *cause* the effort. But it does mean the gaps and the pain are in the same place, which is a good argument for fixing the gaps first."

**Watch for.** State the causal caveat before someone else does. Volunteering it costs you nothing and stops the finding being dismissed.

---

### Slide 52 — Judged effort against observed effort

**On screen.** Judged effort by observed-index decile.

**Say.** "The two independent readings, plotted against each other. Spearman 0.346, interval 0.330 to 0.362.

Read the deciles: the bottom tenth by observed effort is 10.3% high-judged; the top tenth is 66.0%. They move together clearly and monotonically, and neither knew anything about the other.

That's corroboration. It is not validation — neither of them is a customer. The next slide is."

**Concept — Spearman correlation.** It measures whether two things move up and down together in rank order, ignoring the shape of the relationship. 0.346 is a real, moderate relationship: knowing the observed index genuinely shifts what you'd expect from the judged score, but nowhere near determines it. That's the honest reading, and it's what you'd expect from two measures that overlap partially.

---

### Slide 53 — What actually predicts how hard the customer found it

**On screen.** Spearman of each signal against the customer's own survey answer, ranked.

**Say.** "This is the only comparison in the deck against an actual customer. 2,813 people answered the effort question on the CSAT survey.

The model reading the conversation: **+0.207**, interval 0.172 to 0.242.

The best handling metric — how many times the customer had to write — **+0.112**.

And then the two metrics an operations team reaches for first: agent handoffs at **minus 0.028**, repeat contact at **minus 0.009**. Both negatively signed, both statistically indistinguishable from zero. They do not measure what the customer felt.

Our own composite index came in at +0.056 — worse than its best single component. Equal weighting diluted the one signal that was working.

The conclusion is uncomfortable and I think it's the most useful thing in Part F: **reading what the customer wrote is roughly twice as informative as anything in the handling record.** If you want to know how hard a ticket was, the transcript tells you and the metadata largely doesn't."

**Watch for.** Two challenges.

*"+0.207 is weak."* It is, in absolute terms — and that's partly the score's own repeatability, which is slide 54. But it's the *relative* comparison that carries the finding, and every signal here faces the same ceiling.

*"2,813 out of 50,000 is a low response rate — is it representative?"* Survey responders are self-selected and we have not corrected for that. Say so. The comparison between signals is still valid because all of them are measured on the same 2,813 people; what's uncertain is whether the absolute levels generalise.

---

### Slide 54 — How repeatable is the effort score?

**On screen.** Nine reliability measures from scoring the same 12,000 tickets twice.

**Say.** "I want to spend a minute here, because this slide changes how you should quote everything else in Part F.

Through an accident in the pipeline, the same 12,000 tickets were scored twice by the same prompt. That gives a clean test-retest measurement, which is normally hard to get.

Exact agreement on the five-level score: 62.3%. Within one level: 98.4%. The two runs correlate at +0.675.

That last number is a ceiling. A measure cannot correlate with anything better than it correlates with itself. So the +0.207 against the customer is operating under a hard cap — corrected for it, the true relationship is somewhere nearer 0.25, but it will never approach 1 with this instrument.

And the practical consequence: the high-effort rate came out at 34.4% in one run and 30.7% in the other. That's 3.7 points of movement from nothing but model variability — larger than any confidence interval in this deck. Those intervals cover sampling error only. They do not include this.

So: quote aggregate effort rates to the nearest few points. And never treat any single ticket's effort score as a fact about that ticket."

**Watch for.** Someone may ask why we're volunteering this. The answer is that if we didn't, someone would rerun it and find it. And the finding is genuinely useful — most published LLM-scoring work never measures test-retest at all. Reporting it is a strength.

*If asked "does this invalidate Part F?"* — No, and be precise about why. It bounds the precision of individual scores and of aggregate rates to a few points. It does not affect the *ordering*, which is what every conclusion in Part F rests on: reasons ranked by effort, rules ranked by effort, and signals ranked against the survey. Rankings survive noise that point estimates don't.

---

### Slide 55 — What effort adds to the recommendations

**On screen.** Four blocks re-reading Parts D and E through customer cost.

**Say.** "Pulling Part F back into the recommendations.

**The matrix gaps aren't only a governance problem.** Tickets no rule covers run at 23.4% high-effort against 21.3% where rule and code agree — and where the code is unclaimable, 38.9%.

**Rule/code disagreement tracks a harder experience** — 35.0%, nearly 14 points above baseline. The bookkeeping mismatch is visible to the customer.

**Being redirected elsewhere is a first-class outcome here.** It needed a friction category of its own and didn't have one.

**And operational effort metrics do not measure customer effort.** Handoffs and repeat contact are negatively signed against the customer's own answer. If effort is being reported off handling metrics anywhere in the organisation, that reporting is measuring something other than what it claims to."

**Watch for.** That last point is the one most likely to land somewhere sensitive. Deliver it as a finding about the metrics, not about anyone's dashboard, and offer the qualification honestly: it's 2,813 self-selected respondents on one product's rejected tickets. It is not a general law of support operations.

---

# Appendix (slides 56–63)

> Do not present these. They exist so that when someone asks "what about rule 17?" you can turn to a slide instead of promising a follow-up.

### Slide 56 — Appendix divider
Reference material: full tables, method detail, and the limitations that bound every number.

### Slides 57–58 — Conformance by validation rule
All 22 rules with sample n, expected code, strict and loose rates, and whether they're estimable (≥30 sampled tickets).
**Use it when:** someone asks about a specific rule.
**Points to have ready:** CSDVR1.6 (rule 06) is the best performer at 95%. CSDVR1.8 (rule 08) shows the 2% / 85% split — finding 2. CSDVR1.14 (rule 14) is 96% but on only 303 tickets. Everything on slide 58 below CSDVR2.9 has fewer than 30 tickets and is marked *not estimable* — quote those as illustrative only, never as rates.

### Slide 59 — Conformance by resolution code
**Points to have ready:** 'advice request' is 61% no-rule-applies and 0% conformance by construction — it's unmappable. 'Others' is 47% no-rule-applies, which is the wastebasket showing up in the data. 'reevaluation' is the cleanest code at 98%.

### Slide 60 — The rejection-reason taxonomy
All 17 leaves in 5 groups with sample n and population estimate. Use it if someone asks what a category contains, or why there are four "Other" leaves — those are the residual bins each group needs so that forcing a fit is never required.

### Slide 61 — Prompt corrections and their effect
The full record of what was changed and what it moved. **Use it when challenged on tuning.** The key line is at the bottom: the headline moved 67% → 75–79% across three rounds, and the difference between the last two probes was inside the ±3.1-point interval of a 1,000-ticket sample. Tuning stopped there deliberately, not when the number looked good.

### Slide 62 — Limitations
Five, each bounding how the numbers should be read: the reference standard is agent-assigned; the matrix is one analyst's interpretation (quoted from its own Legend sheet); 6,214 tickets were never classified and skew towards advice requests; the model returned an out-of-taxonomy code on 28 tickets (0.23%), reported as a separate bucket rather than dropped; and it's a single model, single pass, with no human adjudication.
**If you have time for one appendix slide, make it this one** — presenting your own limitations before they're extracted from you is worth more than any result on the slide before it.

### Slide 63 — Reproducibility
Every artefact and its path. Sample seed 0, stratified by resolution code, floor 300. The run is resumable and re-running with an unchanged prompt makes no further LLM calls. **Use it when** someone asks to check the work — the answer is "here are the seven paths", not "I'll send you something".

---

# Closing

If you need a single closing line: *"The matrix is a real description of practice — the associations confirm that. It has four specific holes, they total roughly ten thousand tickets a year, and the tickets in those holes are also the ones that cost customers the most. The cheapest fix is a mapping swap that moves three and a half thousand tickets a year without touching a single ticket."*

**The ask, in order of value:**
1. A Content specialist spends two hours on the 30 disagreement cases in the workbook.
2. A decision on rule 08's primary code.
3. A decision on whether enquiries need a rule, a disposition, or something else.

<!-- slide numbers renumbered for the 63-slide deck -->
