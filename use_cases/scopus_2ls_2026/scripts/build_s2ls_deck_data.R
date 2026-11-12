# Statistics and regression models for the Scopus Content 2LS back-and-forth deck.
#
# Run with R 4.6:
#
#   & "C:\Program Files\R\R-4.6.1\bin\Rscript.exe" scripts\build_s2ls_deck_data.R
#
# Needs jsonlite, writexl and sandwich (plus MASS, which ships with R). On this machine they
# live in the R 4.3 user library, which is added to the search path below; they load fine
# under 4.6. readxl does not (its DLL was built for 4.3), so the input is read as CSV.
#
# Reads the weighted sample deliverable written by notebook 17 - the companion CSV
# runs/output/scopus_2ls_2026_escalation_effort_sample_with_transcripts.csv, which holds the
# same rows and columns as the xlsx "tickets" sheet plus the transcripts - and writes:
#
#   runs/output/s2ls_deck/deck_data.json          every number the deck shows
#   runs/output/s2ls_deck/s2ls_effort_models.xlsx full coefficient tables
#
# The deck itself is rendered by scripts/build_s2ls_deck.py (python-pptx), which only
# reads deck_data.json.
#
# Definitions
# -----------
# * A tier crossing is one move of the case across the 1LS/2LS boundary: a hand-off
#   1LS -> 2LS (n_handoffs_to_2ls) or a return 2LS -> 1LS (n_returns_from_2ls). Both are
#   recounted from the LLM's event list, where each event carries a verbatim quote.
# * Patterns: 0 crossings = not escalated; 1 = one-way (handed off, nothing visible came
#   back); 2 = a round trip; 3+ = back-and-forth.
# * extra_crossings = crossings beyond a round trip (crossings - 2, floored at 0). It is the
#   exposure, with not-escalated and one-way absorbed by their own indicators so they
#   cannot bend the slope. One-way tickets carry MORE effort than round trips (nothing
#   came back), so a single linear crossings term would understate the effect.
#
# Models (all control for year, contact reason, resolution code, channel, customer type)
# -----------------------------------------------------------------------------------
# * effort     ordinal logit (MASS::polr) on the LLM effort score, very_high folded into high
# * days_open  OLS on log(1 + days from first to last message)
# * cust_msgs  Poisson GLM on customer messages
# * followups  Poisson GLM on customer follow-ups after the first agent reply
# Primary estimates are unweighted with the sampling strata as fixed effects: the design
# variables are controlled, so conditional effects need no weights. Standard errors are
# HC1-robust (sandwich). A survey-weighted re-fit is reported as a sensitivity check.

local({
  user_lib <- file.path(Sys.getenv("LOCALAPPDATA"), "R", "win-library", "4.3")
  if (dir.exists(user_lib)) .libPaths(c(.libPaths(), user_lib))
})
suppressPackageStartupMessages({
  library(jsonlite)
  library(writexl)
  library(MASS)
  library(sandwich)
})

base_dir <- local({
  f <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE))
  if (length(f)) normalizePath(file.path(dirname(f), "..")) else getwd()
})
SRC      <- file.path(base_dir, "runs", "output", "scopus_2ls_2026_escalation_effort_sample_with_transcripts.csv")
OUT_DIR  <- file.path(base_dir, "runs", "output", "s2ls_deck")
OUT_JSON <- file.path(OUT_DIR, "deck_data.json")
OUT_XLSX <- file.path(OUT_DIR, "s2ls_effort_models.xlsx")
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

PATTERNS      <- c("Not escalated", "One-way", "Round trip", "3 crossings", "4+ crossings")
EFFORT_MAP    <- c(very_low = 0, low = 1, medium = 2, high = 3, very_high = 3)
EFFORT_LABELS <- c("Very low", "Low", "Medium", "High")
CONTROLS      <- "year + cr1_rep + rc_rep + channel + cust_type"
EXPOSURE      <- "extra_crossings + not_escalated + one_way"

# ─────────────────────────────────────────────────────────────── data
as_flag <- function(x) toupper(as.character(x)) %in% c("TRUE", "1", "1.0")
nz      <- function(x) ifelse(is.na(x), 0, x)

t <- read.csv(SRC, encoding = "UTF-8", check.names = FALSE, stringsAsFactors = FALSE,
              na.strings = c("", "NA"))
transcripts <- setNames(t$transcript_full, t$INCIDENT_REF)  # kept for the verbatim quotes
t$transcript_full <- NULL
t$handoffs        <- nz(t$n_handoffs_to_2ls)
t$returns         <- nz(t$n_returns_from_2ls)
t$crossings       <- t$handoffs + t$returns
t$pattern         <- factor(as.character(cut(t$crossings, c(-Inf, 0, 1, 2, 3, Inf), labels = PATTERNS)),
                            levels = PATTERNS)
t$not_escalated   <- as.integer(t$crossings == 0)
t$one_way         <- as.integer(t$crossings == 1)
t$extra_crossings <- pmax(t$crossings - 2, 0)
t$back_and_forth  <- t$crossings >= 3
# Decomposition of the crossings (escalated tickets only; 0 for not-escalated):
# re-routing loops (1LS sends it to 2LS again) vs extra returns from 2LS (interim updates,
# information requests, rejections relayed back). no_return flags a hand-off with nothing back.
t$extra_handoffs  <- pmax(t$handoffs - 1, 0)
t$extra_returns   <- pmax(t$returns - 1, 0)
t$no_return       <- as.integer(t$handoffs > 0 & t$returns == 0)
t$bf_type         <- ifelse(!t$back_and_forth, "none",
                            ifelse(t$handoffs >= 2, "Re-routed to 2LS again", "Extra 2LS returns only"))
t$effort          <- unname(EFFORT_MAP[t$s2_effort_score])
t$effort_f        <- factor(t$effort, levels = 0:3, ordered = TRUE)
t$effort_med_plus <- as.integer(t$effort >= 2)
t$log_days        <- log1p(t$obs_span_days)
t$year            <- factor(as.character(t$year))
t$cr1_rep         <- factor(t$cr1_rep)
t$rc_rep          <- factor(t$rc_rep)
# Fold rare channel / customer-type levels so no dummy rests on a handful of rows
t$channel   <- factor(ifelse(t$Channel %in% c("Web", "Chat", "CSS Email", "Fax"), t$Channel, "Other"))
ct_n        <- table(t$customer_classification_type)
t$cust_type <- factor(ifelse(ct_n[t$customer_classification_type] >= 50, t$customer_classification_type, "Other"))

stopifnot(!anyNA(t$effort), abs(sum(t$weight) - 63824) < 1)
cat(sprintf("%s sampled tickets, weights sum to %s\n",
            format(nrow(t), big.mark = ","), format(round(sum(t$weight)), big.mark = ",")))

wshare  <- function(mask, w) sum(w * mask) / sum(w)
wmedian <- function(x, w) { o <- order(x); x[o][which(cumsum(w[o]) >= sum(w) / 2)[1]] }

# ─────────────────────────────────────────────────────────────── models
fml <- function(y, expo) as.formula(paste(y, "~", expo, "+", CONTROLS))

hc1 <- function(m) vcovHC(m, type = "HC1")
polr_vcov <- function(m) {
  # sandwich has estfun/bread methods for polr; fall back to the model-based vcov if not
  tryCatch(sandwich(m) * nobs(m) / (nobs(m) - length(coef(m)) - length(m$zeta)),
           error = function(e) { message("polr: robust vcov unavailable, using model-based"); vcov(m) })
}

effect_row <- function(b, se, p, outcome, scale, n) {
  lo <- b - 1.96 * se; hi <- b + 1.96 * se
  list(outcome = outcome, scale = scale, coef = b, se = se, p = p,
       ratio = exp(b), ratio_lo = exp(lo), ratio_hi = exp(hi),
       pct = (exp(b) - 1) * 100, pct_lo = (exp(lo) - 1) * 100, pct_hi = (exp(hi) - 1) * 100, n = n)
}
effect <- function(m, V, term, outcome, scale) {
  b <- unname(coef(m)[term]); se <- sqrt(V[term, term])
  effect_row(b, se, 2 * pnorm(-abs(b / se)), outcome, scale, nobs(m))
}
coef_table <- function(m, V, name) {
  b  <- c(coef(m), if (!is.null(m$zeta)) m$zeta)
  se <- sqrt(diag(V))[names(b)]
  data.frame(model = name, term = names(b), coef = unname(b), se = unname(se),
             p = 2 * pnorm(-abs(b / se)), ci_low = b - 1.96 * se, ci_high = b + 1.96 * se,
             row.names = NULL)
}

n <- nrow(t)
m_eff  <- polr(fml("effort_f", EXPOSURE), data = t, Hess = TRUE, method = "logistic")
m_days <- lm(fml("log_days", EXPOSURE), data = t)
m_msgs <- glm(fml("obs_customer_turns", EXPOSURE), family = poisson, data = t)
m_fup  <- glm(fml("obs_customer_followups", EXPOSURE), family = poisson, data = t)
V_eff <- polr_vcov(m_eff); V_days <- hc1(m_days); V_msgs <- hc1(m_msgs); V_fup <- hc1(m_fup)

effects <- list(
  effect(m_eff,  V_eff,  "extra_crossings", "Higher customer-effort score", "odds ratio"),
  effect(m_days, V_days, "extra_crossings", "Days open (first to last message)", "% change"),
  effect(m_msgs, V_msgs, "extra_crossings", "Customer messages", "rate ratio"),
  effect(m_fup,  V_fup,  "extra_crossings", "Customer follow-ups", "rate ratio")
)

# ---- decomposition: which kind of crossing drives the effect?
DECOMP <- "extra_handoffs + extra_returns + not_escalated + no_return"
md_eff  <- polr(fml("effort_f", DECOMP), data = t, Hess = TRUE, method = "logistic")
md_days <- lm(fml("log_days", DECOMP), data = t)
md_msgs <- glm(fml("obs_customer_turns", DECOMP), family = poisson, data = t)
md_fup  <- glm(fml("obs_customer_followups", DECOMP), family = poisson, data = t)
Vd_eff <- polr_vcov(md_eff)
decomposition <- list()
for (term in c("extra_handoffs", "extra_returns")) {
  lab <- if (term == "extra_handoffs") "Each re-routing to 2LS" else "Each extra return from 2LS"
  decomposition[[term]] <- list(
    label = lab,
    effort    = effect(md_eff,  Vd_eff,        term, "Higher customer-effort score", "odds ratio"),
    days      = effect(md_days, hc1(md_days),  term, "Days open", "% change"),
    msgs      = effect(md_msgs, hc1(md_msgs),  term, "Customer messages", "rate ratio"),
    followups = effect(md_fup,  hc1(md_fup),   term, "Customer follow-ups", "rate ratio"))
}

# ---- sensitivity: survey-weighted re-fit (weights normalised to mean 1; quasi families
# ---- because the weights are not integers)
t$wn <- t$weight / mean(t$weight)
mw_medp <- glm(fml("effort_med_plus", EXPOSURE), family = quasibinomial, data = t, weights = wn)
mw_days <- lm(fml("log_days", EXPOSURE), data = t, weights = wn)
mw_msgs <- glm(fml("obs_customer_turns", EXPOSURE), family = quasipoisson, data = t, weights = wn)
mw_fup  <- glm(fml("obs_customer_followups", EXPOSURE), family = quasipoisson, data = t, weights = wn)
sensitivity <- list(
  effect(mw_medp, hc1(mw_medp), "extra_crossings", "Medium-or-higher effort (weighted logit)", "odds ratio"),
  effect(mw_days, hc1(mw_days), "extra_crossings", "Days open (weighted)", "% change"),
  effect(mw_msgs, hc1(mw_msgs), "extra_crossings", "Customer messages (weighted)", "rate ratio"),
  effect(mw_fup,  hc1(mw_fup),  "extra_crossings", "Customer follow-ups (weighted)", "rate ratio")
)

# ---- average predictions by pattern: every ticket set to that pattern, controls as observed,
# ---- averaged with the survey weights so the answer describes the population mix
t$pattern_rt <- relevel(t$pattern, ref = "Round trip")
mc_eff  <- polr(fml("effort_f", "pattern_rt"), data = t, Hess = TRUE, method = "logistic")
mc_days <- lm(fml("log_days", "pattern_rt"), data = t)
mc_msgs <- glm(fml("obs_customer_turns", "pattern_rt"), family = poisson, data = t)
w <- t$weight / sum(t$weight)
predictions <- list()
for (p in PATTERNS) {
  nd <- t
  nd$pattern_rt <- factor(p, levels = levels(t$pattern_rt))
  probs <- predict(mc_eff, newdata = nd, type = "probs")
  predictions[[p]] <- list(
    p_medium_plus = sum(rowSums(probs[, 3:4]) * w),
    p_high        = sum(probs[, 4] * w),
    # log-scale OLS back-transformed without smearing: a "typical" (geometric-mean) days open.
    # Duan smearing overstated the observed means (41.5 vs 34.8 days for a round trip).
    days_open     = sum(expm1(predict(mc_days, newdata = nd)) * w),
    customer_msgs = sum(predict(mc_msgs, newdata = nd, type = "response") * w)
  )
}

for (e in c(effects, sensitivity))
  cat(sprintf("  %-44s x%.2f [%.2f, %.2f]  p=%.2g\n", e$outcome, e$ratio, e$ratio_lo, e$ratio_hi, e$p))
for (d in decomposition)
  cat(sprintf("  %-28s effort x%.2f  days x%.2f  msgs x%.2f  follow-ups x%.2f\n", d$label,
              d$effort$ratio, d$days$ratio, d$msgs$ratio, d$followups$ratio))
for (p in PATTERNS) with(predictions[[p]],
  cat(sprintf("  %-14s P(med+)=%.1f%%  P(high)=%.1f%%  days=%.1f  msgs=%.2f\n",
              p, 100 * p_medium_plus, 100 * p_high, days_open, customer_msgs)))

# ─────────────────────────────────────────────────────────────── descriptives
N   <- sum(t$weight)
esc <- t[t$crossings > 0, ]
bf  <- t[t$back_and_forth, ]

patterns <- lapply(PATTERNS, function(p) {
  g <- t[t$pattern == p, ]
  list(pattern = p, share = sum(g$weight) / N, est = sum(g$weight), sampled = nrow(g))
})

by_pattern <- lapply(PATTERNS, function(p) {
  g <- t[t$pattern == p, ]; gw <- g$weight
  list(pattern = p,
       effort_mix = sapply(0:3, function(k) wshare(g$effort == k, gw)),
       median_days = wmedian(g$obs_span_days, gw),
       mean_customer_msgs = weighted.mean(g$obs_customer_turns, gw),
       mean_followups = weighted.mean(g$obs_customer_followups, gw),
       mean_chase = weighted.mean(nz(g$s2_customer_chase_count), gw),
       resolved = wshare(g$s2_resolution_outcome %in% "resolved", gw),
       sentiment_negative = wshare(g$s2_customer_sentiment_end %in% "negative", gw),
       deadline = wshare(as_flag(g$s2_deadline_pressure), gw),
       chasing_friction = wshare(as_flag(g$fr_customer_chasing), gw),
       sampled = nrow(g))
})

# where back-and-forth concentrates (groups with >= min_n sampled tickets)
rate_by <- function(col, min_n) {
  rows <- lapply(split(t, t[[col]], drop = TRUE), function(g) {
    if (nrow(g) < min_n) return(NULL)
    e <- g[g$crossings > 0, ]
    list(group = as.character(g[[col]][1]), sampled = nrow(g), est = sum(g$weight),
         escalated = wshare(g$crossings > 0, g$weight),
         bf_of_escalated = if (nrow(e)) wshare(e$back_and_forth, e$weight) else NA,
         bf_of_all = wshare(g$back_and_forth, g$weight))
  })
  rows <- Filter(Negate(is.null), rows)
  unname(rows[order(-sapply(rows, `[[`, "est"))])
}

top_shares <- function(x, w, k, key) {
  s <- sort(tapply(w, x, sum), decreasing = TRUE) / sum(w)
  s <- head(s, k)
  unname(Map(function(nm, v) setNames(list(nm, unname(v)), c(key, "share")), names(s), s))
}

grounded_cols <- grep("_grounded$", names(t), value = TRUE)
desc <- list(
  N = N, n_sampled = nrow(t),
  escalated_share = wshare(t$crossings > 0, t$weight),
  bf_share_all = wshare(t$back_and_forth, t$weight),
  bf_share_escalated = wshare(esc$back_and_forth, esc$weight),
  bf_est = sum(bf$weight),
  reescalated_share_escalated = wshare(esc$handoffs >= 2, esc$weight),
  info_request_share_escalated = wshare(grepl("info_request_from_2ls", esc$s2_events_sequence), esc$weight),
  mean_crossings_escalated = weighted.mean(esc$crossings, esc$weight),
  bf_types = lapply(c("Re-routed to 2LS again", "Extra 2LS returns only"), function(k) {
    g <- t[t$bf_type == k, ]
    list(type = k, share_all = sum(g$weight) / N, share_of_bf = sum(g$weight) / sum(bf$weight),
         est = sum(g$weight), sampled = nrow(g),
         effort_med_plus = wshare(g$effort >= 2, g$weight), effort_high = wshare(g$effort == 3, g$weight))
  }),
  patterns = patterns,
  by_pattern = by_pattern,
  by_contact_reason = rate_by("cr1_rep", 100),
  by_resolution_code = rate_by("rc_rep", 100),
  by_year = rate_by("year", 1),
  journey_escalated = top_shares(esc$s2_journey, esc$weight, 8, "journey"),
  bf_sequences = top_shares(bf$s2_events_sequence, bf$weight, 6, "sequence"),
  grounded_min = min(sapply(grounded_cols, function(c) mean(as_flag(t[[c]]))))
)

# ─────────────────────────────────────────────────────────────── quotes
# Back-and-forth tickets whose first events quote no names or addresses, for the
# "what a loop looks like" slide.
ev_cols <- grep("^s2_handoff_events_evidence_\\d+$", names(t), value = TRUE)
ev_cols <- ev_cols[order(as.integer(sub(".*_", "", ev_cols)))]
set.seed(0)
quotes <- list()
for (i in sample(which(t$back_and_forth))) {
  ev <- unlist(t[i, ev_cols]); ev <- ev[!is.na(ev) & nzchar(trimws(ev))]
  if (length(ev) < 3) next
  ev <- head(ev, 4)
  if (any(nchar(ev) >= 140 | grepl("Dear|@", ev))) next
  kinds <- unlist(t[i, sub("evidence", "event", names(ev))])
  quotes[[length(quotes) + 1]] <- list(
    ref = t$INCIDENT_REF[i],
    events = unname(Map(function(k, q) list(event = k, quote = q), kinds, ev)))
  if (length(quotes) >= 6) break
}

# ─────────────────────────────────────────────────────────────── verbatim evidence
# For every insight in the deck: one customer sentence and one agent sentence, verbatim,
# from the same ticket, each tagged with its turn and date.
#
# Quotes are whole sentences cut from the rebuilt transcript turns (HTML and email signatures
# already stripped by notebook 17), never the LLM's paraphrase, so they are verbatim by
# construction and the speaker is known from the turn header. A sentence is only eligible
# when it carries nothing identifying: no name used in a greeting anywhere in that ticket,
# no email, URL, DOI, long number or quoted article title. Candidate tickets are shuffled with
# a fixed seed; the first ticket with both a qualifying customer and agent sentence wins, and
# the next candidates go to the workbook so any quote can be swapped.

HEADER_RE <- "\\[T(\\d+) \\| (\\d{4}-\\d{2}-\\d{2})(?: \\| \\+\\d+d)? \\| ([^\\]]+)\\] "
HONORIFICS <- c("Dear", "Dr", "Prof", "Professor", "Mr", "Mrs", "Ms", "Miss", "Sir", "Madam", "Customer",
                "Team", "Colleague", "Colleagues", "Author", "Editor", "Hello", "Hi", "All", "Scopus",
                "Support", "Elsevier", "Good", "Day", "Morning", "Afternoon")

parse_turns <- function(ref, txt) {
  m <- gregexpr(HEADER_RE, txt, perl = TRUE)[[1]]
  if (m[1] == -1) return(NULL)
  heads <- regmatches(txt, list(m))[[1]]
  ends  <- c(m[-1] - 1, nchar(txt))
  body  <- substring(txt, m + attr(m, "match.length"), ends)
  parts <- regmatches(heads, regexec(HEADER_RE, heads, perl = TRUE))
  data.frame(ref = ref, turn = as.integer(sapply(parts, `[`, 2)), date = sapply(parts, `[`, 3),
             speaker = sapply(parts, `[`, 4), body = body, stringsAsFactors = FALSE)
}

greeting_names <- function(txt) {
  g <- regmatches(txt, gregexpr("(?:Dear|Hi|Hello|Hallo|Thank you|Thanks)[ ,]+(?:[A-Z][\\w'.-]*\\.? ?){1,4}",
                                txt, perl = TRUE))[[1]]
  tok <- unlist(strsplit(gsub("[,.]", " ", g), "\\s+"))
  unique(tok[nchar(tok) >= 3 & grepl("^[A-Z]", tok) & !tok %in% HONORIFICS])
}

BAD_RE <- paste0("@|https?://|www\\.|10\\.\\d{4,}/|\\d{5,}|\\bDear\\b|[Rr]egards|\\bID\\b|",
                 "[\"“”][^\"“”]{25,}[\"“”]|\\[|\\.\\.\\.|…")
# Email boilerplate, and institution names that could identify the customer
JUNK_RE <- paste0("(?i)confidential|virus|intended (only|solely)|disclaimer|unsubscribe|this e-?mail|",
                  "notify the sender|external email|do not click|\\|\\s|\\(\\w+\\.com\\)|",
                  "\\b(universit|institut|college|council|hospital|academy)")
ok_sentence <- function(s, names) {
  ascii <- nchar(gsub("[^A-Za-z ]", "", s)) / pmax(nchar(s), 1)
  keep <- nchar(s) >= 45 & nchar(s) <= 230 & ascii > 0.8 & !grepl(BAD_RE, s, perl = TRUE) &
    !grepl(JUNK_RE, s, perl = TRUE) &
    grepl("^[A-Z]", s) & grepl("[.!?:]$", s)          # whole sentences only; drops quoted "> ..." lines
  if (length(names))
    keep <- keep & !grepl(paste0("\\b(", paste(names, collapse = "|"), ")\\b"), s, perl = TRUE)
  keep
}

cat("Building the sentence pool from", length(transcripts), "transcripts...\n")
pool <- do.call(rbind, lapply(names(transcripts), function(ref) {
  tr <- parse_turns(ref, transcripts[[ref]])
  if (is.null(tr)) return(NULL)
  tr <- tr[tr$speaker == "Customer" | startsWith(tr$speaker, "Agent"), ]
  if (!nrow(tr)) return(NULL)
  nm <- greeting_names(transcripts[[ref]])
  agent_text <- paste(tr$body[tr$speaker != "Customer"], collapse = " ")
  rows <- lapply(seq_len(nrow(tr)), function(i) {
    s <- trimws(unlist(strsplit(tr$body[i], "(?<=[.!?])\\s+|\\n+", perl = TRUE)))
    s <- s[ok_sentence(s, nm)]
    # a "customer" sentence that also appears in an agent turn is quoted history, not the customer
    if (tr$speaker[i] == "Customer" && length(s))
      s <- s[!vapply(s, function(x) grepl(x, agent_text, fixed = TRUE), logical(1))]
    if (!length(s)) return(NULL)
    data.frame(ref = ref, turn = tr$turn[i], date = tr$date[i],
               who = ifelse(tr$speaker[i] == "Customer", "customer", "agent"), sentence = s,
               stringsAsFactors = FALSE)
  })
  do.call(rbind, rows)
}))
cat(sprintf("  %s eligible sentences (%s customer, %s agent)\n", format(nrow(pool), big.mark = ","),
            format(sum(pool$who == "customer"), big.mark = ","), format(sum(pool$who == "agent"), big.mark = ",")))

# Reusable phrase patterns (case-insensitive)
RE_REQUEST  <- "(please|kindly|could you|can you|would you|request|need).{0,80}(add|index|correct|update|include|merge|link|fix|change)"
RE_HANDOFF  <- "(raised|forwarded|contacted|escalated|reached out|endorsed|referred|initiated the process|sent).{0,80}(technical|relevant|second|specialist|content|department|team|database|process)"
RE_AT_1LS   <- "(I can confirm|is (now )?(available|indexed|visible|linked)|already (indexed|available|appears|in scopus)|you (can|may) (use|add|search)|feedback wizard|is not (indexed|covered)|does not (index|cover))"
RE_PUSHBACK <- "(still (not|no|missing|wrong|incorrect|waiting|shows?)|not (yet|been) (resolved|fixed|added|updated|linked|corrected|indexed)|same (issue|problem|response|answer)|no (update|progress|response|reply)|(\\d+|several|many|three|four|five|six) (weeks|months))"
# the re-raise itself, not "thank you for reaching out again"
RE_AGAIN    <- "((raised|forwarded|followed up|escalated|sent|reached out)[^.]{0,60}(again|once more)|(again|once more)[^.]{0,40}(technical|relevant) team|re-?raised|re-?escalat|followed up (with|to) (our|the) (technical|relevant)|expedite)"
RE_RELAY    <- "(as per (our|the)|according to (our|the)|(technical|relevant) team (has|have|had) (confirmed|advised|informed|responded|replied)|received (the|a|an) (response|update|feedback)|remains open|still (working|in progress|being processed))"
RE_ASKINFO  <- "(kindly|please|could you|may we|may I|would you) (provide|share|send|confirm|advise|attach)"
RE_SUPPLY   <- "(attached|attachment|as requested|here (is|are)|please find|below (is|are)|I have (sent|provided|attached)|already (sent|provided))"
RE_CORRECT  <- "(correct|amend|update|change).{0,80}(initiated|raised|technical|process|team)"
RE_WRONG    <- "(still|not (been )?(corrected|updated|changed|fixed|resolved)|wrong|incorrect|mistake|error)"
RE_CHASE    <- "(any update|any news|follow(ing)?[- ]up|still waiting|haven.?t (heard|received)|no (response|reply|answer)|reminder|when will|how long|status of)"
RE_SORRY    <- "(apolog|sorry|regret).{0,80}(delay|inconvenience|wait|time)"
RE_LONG     <- "((\\d+|several|many|few|two|three|four|five|six) (weeks|months)|(long|too long|such a long) time|since (january|february|march|april|may|june|july|august|september|october|november|december|last))"
# an explicit timeframe promise, to set against the customer's months of waiting
RE_TIMEFRAME <- "((may|will|could) take|up to|within|allow).{0,30}(weeks|days|business days)"
RE_UNHAPPY  <- "(disappoint|frustrat|unacceptable|not (satisfied|happy|acceptable)|unfortunately|still not|no one|nobody|again and again|very long|ridiculous|annoy|unfair)"
RE_REFUSE   <- "(unable to|cannot|can.?t|not (be )?possible|regret|unfortunately|not able to|outside (the )?coverage|not covered|not eligible)"
# "evaluation" and bare "defense" are excluded: Scopus title (re-)evaluation and journal names hit them
RE_DEADLINE <- "(deadline|promotion|thesis defen[cs]e|grant application|urgent|as soon as possible|asap|appraisal|tenure|performance review)"
RE_URGENT   <- "(urgen|priorit|expedite|as soon as possible|escalat)"

SPECS <- list(
  list(id = "escalated",      filt = t$pattern == "Round trip",            cust = RE_REQUEST,  agent = RE_HANDOFF),
  list(id = "not_escalated",  filt = t$pattern == "Not escalated",         cust = RE_REQUEST,  agent = RE_AT_1LS,
       agent_not = RE_HANDOFF),
  list(id = "rerouted",       filt = t$bf_type == "Re-routed to 2LS again", cust = RE_PUSHBACK, agent = RE_AGAIN),
  list(id = "extra_returns",  filt = t$bf_type == "Extra 2LS returns only", cust = RE_CHASE,    agent = RE_RELAY),
  list(id = "info_not_recd",  filt = t$back_and_forth & t$rc_rep == "Additional Customer Information Not Recd",
       cust = RE_SUPPLY, agent = RE_ASKINFO),
  list(id = "correction_tool", filt = t$back_and_forth & t$rc_rep == "Correction Tool used",
       cust = RE_WRONG, agent = RE_CORRECT),
  list(id = "followups",      filt = t$back_and_forth & t$obs_customer_followups >= 2, cust = RE_CHASE, agent = RE_SORRY),
  list(id = "time_open",      filt = t$crossings >= 3 & t$obs_span_days >= 60,  cust = RE_LONG, agent = RE_TIMEFRAME),
  list(id = "negative_end",   filt = t$crossings >= 3 & t$s2_customer_sentiment_end %in% "negative",
       cust = RE_UNHAPPY, agent = RE_REFUSE),
  list(id = "deadline",       filt = t$crossings >= 3 & as_flag(t$s2_deadline_pressure), cust = RE_DEADLINE,
       agent = RE_URGENT),
  list(id = "rerouting_cost", filt = t$bf_type == "Re-routed to 2LS again" & t$effort >= 2, cust = RE_CHASE,
       agent = RE_HANDOFF)
)

# How strongly a sentence speaks to the insight: distinct pattern hits, then a mild preference
# for mid-length sentences (a bare fragment and a paragraph both read badly on a slide).
hits  <- function(re, x) lengths(regmatches(x, gregexpr(re, x, ignore.case = TRUE, perl = TRUE)))
score <- function(re, x) hits(re, x) - abs(nchar(x) - 120) / 400

pick_pairs <- function(spec, n_keep = 6) {
  refs <- t$INCIDENT_REF[spec$filt %in% TRUE]
  s  <- pool[pool$ref %in% refs, ]
  cu <- s[s$who == "customer" & grepl(spec$cust, s$sentence, ignore.case = TRUE, perl = TRUE), ]
  ag <- s[s$who == "agent" & grepl(spec$agent, s$sentence, ignore.case = TRUE, perl = TRUE), ]
  if (!is.null(spec$agent_not)) ag <- ag[!grepl(spec$agent_not, ag$sentence, ignore.case = TRUE, perl = TRUE), ]
  # a thank-you is courtesy, not evidence of effort
  cu <- cu[!grepl("^(thank|many thanks|i appreciate|we appreciate)", cu$sentence, ignore.case = TRUE), ]
  if (!nrow(cu) || !nrow(ag)) return(list())
  cu$score <- score(spec$cust, cu$sentence); ag$score <- score(spec$agent, ag$sentence)
  best_cu <- cu[order(cu$ref, -cu$score), ]; best_cu <- best_cu[!duplicated(best_cu$ref), ]
  best_ag <- ag[order(ag$ref, -ag$score), ]; best_ag <- best_ag[!duplicated(best_ag$ref), ]
  both <- merge(best_cu, best_ag, by = "ref", suffixes = c("_c", "_a"))
  if (!nrow(both)) return(list())
  set.seed(20260928)                                  # ties broken reproducibly
  both <- both[order(-(both$score_c + both$score_a), sample(nrow(both))), ]
  lapply(seq_len(min(n_keep, nrow(both))), function(i) with(both[i, ], list(
    ticket = ref,
    customer = list(quote = sentence_c, turn = turn_c, date = date_c),
    agent = list(quote = sentence_a, turn = turn_a, date = date_a))))
}

evidence <- list(); evidence_candidates <- list(); used <- character()
for (sp in SPECS) {
  cands <- pick_pairs(sp)
  if (!length(cands)) { message("no quote pair found for ", sp$id); next }
  # each insight gets its own ticket, so no single conversation carries two points
  fresh <- Filter(function(c) !c$ticket %in% used, cands)
  if (length(fresh)) cands <- c(fresh, Filter(function(c) c$ticket %in% used, cands))
  used <- c(used, cands[[1]]$ticket)
  evidence[[sp$id]] <- cands[[1]]
  evidence_candidates[[sp$id]] <- do.call(rbind, lapply(seq_along(cands), function(i) with(cands[[i]], data.frame(
    insight = sp$id, rank = i, ticket = ticket,
    customer_turn = customer$turn, customer_quote = customer$quote,
    agent_turn = agent$turn, agent_quote = agent$quote))))
  cat(sprintf("  %-16s %d candidate pairs; using %s\n", sp$id, length(cands), cands[[1]]$ticket))
}

# ─────────────────────────────────────────────────────────────── write
D <- list(
  meta = list(source = "runs/output/scopus_2ls_2026_escalation_effort_sample_with_transcripts.csv",
              controls = CONTROLS, patterns = PATTERNS, effort_labels = EFFORT_LABELS,
              generated_by = "scripts/build_s2ls_deck_data.R"),
  desc = desc,
  models = list(
    effects = effects, sensitivity = sensitivity, predictions = predictions,
    decomposition = decomposition,
    effort_one_way = effect(m_eff, V_eff, "one_way", "One-way vs round trip", "odds ratio"),
    effort_not_escalated = effect(m_eff, V_eff, "not_escalated", "Not escalated vs round trip", "odds ratio")),
  quotes = quotes,
  evidence = evidence
)
write_json(D, OUT_JSON, auto_unbox = TRUE, digits = NA, pretty = TRUE, na = "null")

rows_df <- function(lst) do.call(rbind, lapply(lst, as.data.frame))
write_xlsx(list(
  effects_per_extra_crossing = rows_df(effects),
  sensitivity_weighted       = rows_df(sensitivity),
  predictions_by_pattern     = cbind(pattern = PATTERNS, rows_df(predictions)),
  decomposition              = do.call(rbind, lapply(decomposition, function(d)
                                 cbind(crossing = d$label, rows_df(d[c("effort", "days", "msgs", "followups")])))),
  quote_candidates           = do.call(rbind, unname(evidence_candidates)),
  effort_ordinal             = coef_table(m_eff, V_eff, "effort_ordinal"),
  days_ols                   = coef_table(m_days, V_days, "days_ols"),
  msgs_poisson               = coef_table(m_msgs, V_msgs, "msgs_poisson"),
  followups_poisson          = coef_table(m_fup, V_fup, "followups_poisson")
), OUT_XLSX)
cat(sprintf("Wrote %s and %s\n", OUT_JSON, OUT_XLSX))
