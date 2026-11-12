# Customer-effort regression models.
#
#   & "C:\Program Files\R\R-4.3.1\bin\Rscript.exe" scripts\effort_model.R
#
# Outcome is the customer's own survey answer. Models are nested so that each
# block's contribution is testable by likelihood-ratio test.
#
# Two arms, deliberately kept apart:
#   S0 -> S1 -> S2   structural, then + the LLM's reading, n = 2,813
#   R0 -> R1 -> R2   + validation rules and rejection reasons, n = 625
# and L1, the LLM's own high-effort call on the design-weighted 12,000.
#
# Writes tidy CSVs and model_results.json to runs/output/model/.

suppressPackageStartupMessages({
  library(MASS); library(car); library(pROC); library(survey)
  library(jsonlite); library(dplyr)
})

set.seed(20260903)
BASE <- getwd()
stopifnot(dir.exists(file.path(BASE, "runs")))   # run from the project root
OUTDIR <- file.path(BASE, "runs", "output", "model")

cat(strrep("=", 78), "\nEFFORT MODELS (R", as.character(getRversion()), ")\n",
    strrep("=", 78), "\n", sep = "")

d <- read.csv(file.path(OUTDIR, "effort_model_input.csv"), stringsAsFactors = FALSE)
cat(sprintf("  frame %d x %d\n", nrow(d), ncol(d)))

# ───────────────────────────────────────────────────────── analysis samples
A <- d[d$in_analysis == 1, ]
stopifnot(nrow(A) == 2813, sum(A$survey_not_easy) == 360, sum(A$survey_hard) == 216)

# Missing predictors are imputed with an explicit indicator rather than dropped:
# dropping would break the nested likelihood-ratio tests, which require identical
# rows across models.
A$frt_missing <- as.integer(is.na(A$log_frt_days))
A$log_frt_days[A$frt_missing == 1] <- median(A$log_frt_days, na.rm = TRUE)
A$resolution_transparency[is.na(A$resolution_transparency)] <- "unknown"

fac <- c("resolution_code", "contact_reason_l1", "channel", "customer_type",
         "close_half", "repeat_contact_obs", "resolution_transparency",
         "effort_class_l1")
for (f in fac) if (f %in% names(A)) A[[f]] <- factor(A[[f]])
# Reference levels chosen to be the common, benign case so odds ratios read as
# "compared with an ordinary ticket".
A$repeat_contact_obs <- relevel(A$repeat_contact_obs, ref = "no")
A$resolution_transparency <- relevel(A$resolution_transparency, ref = "transparent")

FR <- grep("^fr_", names(A), value = TRUE)
stopifnot(!"obs_effort_index" %in% names(A))

R <- A[A$has_rule == 1, ]
stopifnot(nrow(R) == 625)
R$conformance_status <- factor(R$conformance_status)
R$conformance_status <- relevel(R$conformance_status, ref = "rule matches code")
# The least effortful common reason makes the natural baseline: every other reason
# then reads as "how much harder than a straightforward already-indexed answer".
REASON_REF <- "Content Already Indexed"
R$reason_grp <- factor(R$reason_grp)
stopifnot(REASON_REF %in% levels(R$reason_grp))
R$reason_grp <- relevel(R$reason_grp, ref = REASON_REF)
cat(sprintf("  analysis n=%d (%d not-easy) | rules subset n=%d (%d not-easy)\n",
            nrow(A), sum(A$survey_not_easy), nrow(R), sum(R$survey_not_easy)))

# ───────────────────────────────────────────────────────────── model formulas
# obs_distinct_agents is excluded: it equals obs_agent_handoffs + 1 on 98% of rows
# (r = 0.998), so entering both leaves the design rank-deficient and R silently
# drops one. Handoffs is the interpretable survivor.
B_STRUCT <- c("log_tat_days", "log_frt_days", "frt_missing", "obs_customer_turns",
              "obs_agent_handoffs", "log_span_h", "obs_responses",
              "repeat_contact_obs")
B_CONTEXT <- c("resolution_code", "contact_reason_l1", "channel", "customer_type",
               "close_half")
B_LLM <- c("llm_effort_num", "resolution_transparency", "friction_count", FR)

f_of <- function(y, vars) as.formula(paste(y, "~", paste(vars, collapse = " + ")))

# ─────────────────────────────────────────────────────────────── diagnostics
mcfadden <- function(m) 1 - (m$deviance / m$null.deviance)

epv <- function(m, y) {
  k <- length(coef(m)) - 1
  round(sum(y) / max(k, 1), 2)
}

auc_of <- function(m, y) {
  as.numeric(pROC::auc(pROC::roc(y, fitted(m), quiet = TRUE)))
}

# 5-fold stratified CV. In-sample AUC on 360 events with ~40 terms is optimistic
# by construction, so the out-of-fold figure is the one that counts.
cv_auc <- function(form, data, y, k = 5) {
  yv <- data[[y]]
  idx <- rep(NA_integer_, nrow(data))
  for (cls in c(0, 1)) {
    w <- which(yv == cls)
    idx[w] <- sample(rep(1:k, length.out = length(w)))
  }
  pred <- rep(NA_real_, nrow(data))
  for (i in 1:k) {
    tr <- data[idx != i, ]; te <- data[idx == i, ]
    m <- try(glm(form, data = tr, family = binomial()), silent = TRUE)
    if (inherits(m, "try-error")) next
    pred[idx == i] <- predict(m, newdata = te, type = "response")
  }
  ok <- !is.na(pred)
  if (length(unique(yv[ok])) < 2) return(NA_real_)
  as.numeric(pROC::auc(pROC::roc(yv[ok], pred[ok], quiet = TRUE)))
}

# With an expected pseudo-R2 this low, the question is not "is the AUC high" but
# "is it outside what shuffling the outcome would produce".
perm_null <- function(form, data, y, reps = 200) {
  out <- numeric(reps)
  for (i in seq_len(reps)) {
    dd <- data
    dd[[y]] <- sample(dd[[y]])
    m <- try(glm(form, data = dd, family = binomial()), silent = TRUE)
    out[i] <- if (inherits(m, "try-error")) NA_real_ else auc_of(m, dd[[y]])
  }
  out[!is.na(out)]
}

fits <- list(); summaries <- list(); coefs <- list()

register <- function(tag, m, data, y, label, note = "") {
  yv <- data[[y]]
  e <- epv(m, yv)
  a_in <- auc_of(m, yv)
  a_cv <- cv_auc(formula(m), data, y)
  summaries[[tag]] <<- data.frame(
    model = tag, label = label, outcome = y, n = nrow(data), events = sum(yv),
    terms = length(coef(m)) - 1, epv = e,
    mcfadden_r2 = round(mcfadden(m), 4),
    auc_in_sample = round(a_in, 4), auc_cv5 = round(a_cv, 4),
    aic = round(AIC(m), 1),
    stability = ifelse(e < 5, "UNSTABLE", ifelse(e < 10, "borderline", "ok")),
    note = note, stringsAsFactors = FALSE)
  ct <- summary(m)$coefficients
  coefs[[tag]] <<- data.frame(
    model = tag, term = rownames(ct), estimate = ct[, 1], std_error = ct[, 2],
    z = ct[, 3], p_value = ct[, 4],
    odds_ratio = exp(ct[, 1]),
    or_lo = exp(ct[, 1] - 1.96 * ct[, 2]),
    or_hi = exp(ct[, 1] + 1.96 * ct[, 2]),
    stringsAsFactors = FALSE, row.names = NULL)
  fits[[tag]] <<- m
  cat(sprintf("  %-5s %-46s n=%5d ev=%3d k=%2d EPV=%5.1f R2=%.3f AUC=%.3f cv=%.3f %s\n",
              tag, substr(label, 1, 46), nrow(data), sum(yv),
              length(coef(m)) - 1, e, mcfadden(m), a_in, a_cv,
              ifelse(e < 5, "<< UNSTABLE", "")))
}

cat("\nSurvey outcome - structural, then the model's reading\n")
S0 <- glm(f_of("survey_not_easy", B_STRUCT), data = A, family = binomial())
register("S0", S0, A, "survey_not_easy", "Handling only (TAT, turns, handoffs, repeat)")

S1 <- glm(f_of("survey_not_easy", c(B_STRUCT, B_CONTEXT)), data = A, family = binomial())
register("S1", S1, A, "survey_not_easy", "+ resolution code and request context")

S2 <- glm(f_of("survey_not_easy", c(B_STRUCT, B_CONTEXT, B_LLM)), data = A,
          family = binomial())
register("S2", S2, A, "survey_not_easy", "+ the LLM's reading of the transcript",
         note = "measures agreement with the LLM, not a structural driver")

cat("\nRobustness\n")
SH <- glm(f_of("survey_hard", c(B_STRUCT, B_CONTEXT)), data = A, family = binomial())
register("S1-hard", SH, A, "survey_hard", "S1 spec, stricter outcome (codes 4-5)")

cat("\nValidation rules and rejection reasons - restricted to the tagged sample\n")
B_MIN <- c("log_tat_days", "obs_customer_turns", "repeat_contact_obs")
R0 <- glm(f_of("survey_not_easy", B_MIN), data = R, family = binomial())
register("R0", R0, R, "survey_not_easy", "Minimal controls only")
R1 <- glm(f_of("survey_not_easy", c(B_MIN, "conformance_status")), data = R,
          family = binomial())
register("R1", R1, R, "survey_not_easy", "+ conformance status (grouped rules)")
R2 <- glm(f_of("survey_not_easy", c(B_MIN, "conformance_status", "reason_grp")), data = R,
          family = binomial())
register("R2", R2, R, "survey_not_easy", "+ rejection reason")

# ────────────────────────────────────────────── ordinal fit over the full scale
cat("\nOrdinal (proportional odds) over the full 1-5 scale\n")
A$survey_ord <- factor(A$survey_effort, levels = 1:5, ordered = TRUE)
ord <- MASS::polr(f_of("survey_ord", c(B_STRUCT, B_CONTEXT)), data = A, Hess = TRUE)
oc <- coef(summary(ord))
ord_coefs <- data.frame(
  model = "S1-ordinal", term = rownames(oc), estimate = oc[, 1], std_error = oc[, 2],
  z = oc[, 3], p_value = 2 * pnorm(abs(oc[, 3]), lower.tail = FALSE),
  odds_ratio = exp(oc[, 1]), or_lo = exp(oc[, 1] - 1.96 * oc[, 2]),
  or_hi = exp(oc[, 1] + 1.96 * oc[, 2]), stringsAsFactors = FALSE, row.names = NULL)
coefs[["S1-ordinal"]] <- ord_coefs
cat(sprintf("  S1-ordinal fitted, %d terms, AIC %.1f\n", length(coef(ord)), AIC(ord)))

# brant is not installed, so the proportional-odds assumption is checked directly:
# refit a binary logit at each cut point and compare the slopes. If the assumption
# holds the coefficients should be similar across cuts.
po <- list()
for (cut in 2:5) {
  A$.y <- as.integer(A$survey_effort >= cut)
  if (sum(A$.y) < 30) next
  m <- glm(f_of(".y", c(B_STRUCT, B_CONTEXT)), data = A, family = binomial())
  po[[paste0("cut_", cut)]] <- coef(m)
}
po_mat <- do.call(cbind, po)
common <- intersect(rownames(po_mat), names(coef(ord)))
po_check <- data.frame(term = common, po_mat[common, , drop = FALSE],
                       stringsAsFactors = FALSE, row.names = NULL)
po_check$spread <- apply(po_mat[common, , drop = FALSE], 1, function(r) max(r) - min(r))
cat(sprintf("  proportional-odds check: %d cut points, median slope spread %.2f\n",
            ncol(po_mat), median(po_check$spread, na.rm = TRUE)))

# ─────────────────────────────────── the LLM's own call, design-weighted 12,000
cat("\nThe LLM's high-effort call on the weighted 12,000\n")
W <- d[d$has_rule == 1 & !is.na(d$llm_high), ]
W$frt_missing <- as.integer(is.na(W$log_frt_days))
W$log_frt_days[W$frt_missing == 1] <- median(W$log_frt_days, na.rm = TRUE)
for (f in c("resolution_code", "contact_reason_l1", "channel", "customer_type",
            "close_half", "repeat_contact_obs", "conformance_status", "reason_grp",
            "rule_grp")) W[[f]] <- factor(W[[f]])
W$repeat_contact_obs <- relevel(W$repeat_contact_obs, ref = "no")
# Same reference levels as R1/R2, or the side-by-side driver comparison would be
# contrasting different baselines and read as a disagreement that is not there.
W$conformance_status <- relevel(W$conformance_status, ref = "rule matches code")
W$reason_grp <- relevel(W$reason_grp, ref = REASON_REF)
W <- W[!is.na(W$obs_turns), ]
cat(sprintf("  weighted frame n=%d, weights sum to %.0f\n", nrow(W), sum(W$w)))

des <- svydesign(ids = ~1, strata = ~resolution_code, weights = ~w, data = W)
L1 <- svyglm(f_of("llm_high", c(B_STRUCT, "contact_reason_l1", "channel",
                                "customer_type", "close_half", "conformance_status",
                                "reason_grp")),
             design = des, family = quasibinomial())
lc <- summary(L1)$coefficients
coefs[["L1"]] <- data.frame(
  model = "L1", term = rownames(lc), estimate = lc[, 1], std_error = lc[, 2],
  z = lc[, 3], p_value = lc[, 4], odds_ratio = exp(lc[, 1]),
  or_lo = exp(lc[, 1] - 1.96 * lc[, 2]), or_hi = exp(lc[, 1] + 1.96 * lc[, 2]),
  stringsAsFactors = FALSE, row.names = NULL)
summaries[["L1"]] <- data.frame(
  model = "L1", label = "LLM high-effort call, design-weighted",
  outcome = "llm_high", n = nrow(W), events = sum(W$llm_high), terms = length(coef(L1)) - 1,
  epv = round(sum(W$llm_high) / (length(coef(L1)) - 1), 2), mcfadden_r2 = NA,
  auc_in_sample = round(auc_of(L1, W$llm_high), 4), auc_cv5 = NA, aic = NA,
  stability = "ok", note = "svyglm, strata = resolution code", stringsAsFactors = FALSE)
cat(sprintf("  L1 fitted, %d terms, AUC %.3f\n", length(coef(L1)) - 1,
            auc_of(L1, W$llm_high)))

# ────────────────────────────────────────────────────────── block contributions
cat("\nBlock contributions (likelihood-ratio tests on identical rows)\n")
lr <- function(small, big, name) {
  a <- anova(small, big, test = "LRT")
  data.frame(comparison = name, df = a$Df[2], deviance = round(a$Deviance[2], 2),
             p_value = a$`Pr(>Chi)`[2],
             delta_mcfadden = round(mcfadden(big) - mcfadden(small), 4),
             stringsAsFactors = FALSE)
}
blocks <- rbind(
  lr(glm(survey_not_easy ~ 1, data = A, family = binomial()), S0, "null -> handling"),
  lr(S0, S1, "handling -> + resolution code and context"),
  lr(S1, S2, "context -> + the LLM's reading"),
  lr(R0, R1, "minimal -> + conformance status (n=625)"),
  lr(R1, R2, "conformance -> + rejection reason (n=625)"))
print(blocks, row.names = FALSE)

cat("\nType-II tests within S1\n")
an <- car::Anova(S1, type = 2)
type2 <- data.frame(term = rownames(an), lr_chisq = round(an[, 1], 2), df = an[, 2],
                    p_value = an[, 3], stringsAsFactors = FALSE, row.names = NULL)
print(type2[order(type2$p_value), ], row.names = FALSE)

# ───────────────────────────────────────────────────────────────── diagnostics
vif_of <- function(m, tag) {
  v <- try(car::vif(m), silent = TRUE)
  if (inherits(v, "try-error")) return(NULL)
  if (is.matrix(v)) v <- v[, ncol(v)]
  data.frame(model = tag, term = names(v), vif = round(as.numeric(v), 2),
             flag = ifelse(as.numeric(v) > 5, "HIGH", ""), stringsAsFactors = FALSE)
}
vifs <- do.call(rbind, list(vif_of(S1, "S1"), vif_of(S2, "S2"), vif_of(R2, "R2")))
nhigh <- sum(vifs$flag == "HIGH", na.rm = TRUE)
cat(sprintf("\n  VIF: %d term(s) above 5\n", nhigh))

cat("  permutation null (200 shuffles of the outcome)...\n")
null_s1 <- perm_null(formula(S1), A, "survey_not_easy", 200)
null_r1 <- perm_null(formula(R1), R, "survey_not_easy", 200)
cat(sprintf("  S1 null AUC: median %.3f, 95th pct %.3f  vs observed in-sample %.3f, cv %.3f\n",
            median(null_s1), quantile(null_s1, .95), auc_of(S1, A$survey_not_easy),
            summaries$S1$auc_cv5))

perm <- data.frame(
  model = c("S1", "R1"),
  null_median = c(median(null_s1), median(null_r1)),
  null_p95 = c(quantile(null_s1, .95), quantile(null_r1, .95)),
  observed_in_sample = c(auc_of(S1, A$survey_not_easy), auc_of(R1, R$survey_not_easy)),
  observed_cv5 = c(summaries$S1$auc_cv5, summaries$R1$auc_cv5),
  stringsAsFactors = FALSE)
perm$verdict <- ifelse(perm$observed_cv5 > perm$null_p95,
                       "outside the null", "INSIDE THE NULL - does not predict")
print(perm, row.names = FALSE)

# ───────────────────────────────────────── calibration deciles for the report
dec <- data.frame(p = fitted(S2), y = A$survey_not_easy)
dec$decile <- cut(rank(dec$p, ties.method = "first"), breaks = 10, labels = 1:10)
calib <- aggregate(cbind(p, y) ~ decile, data = dec, FUN = mean)
names(calib) <- c("decile", "predicted", "observed")
calib$n <- as.numeric(table(dec$decile))

# ────────────────────────────────────────── what drives the customer vs the LLM
cs <- do.call(rbind, coefs)
# R2 and L1 are the pair that share the rule and reason terms: same predictors and
# the same reference levels, one fitted on the customer's answer and one on the
# LLM's. S2 would be the wrong left-hand side - it is the structural + LLM model
# and contains no rule or reason terms at all, so the merge would silently drop
# every row the comparison exists to show.
stopifnot(sum(grepl("^(reason_grp|conformance_status)", cs$term[cs$model == "R2"])) > 0)
drivers <- merge(
  cs[cs$model == "R2", c("term", "odds_ratio", "or_lo", "or_hi", "p_value")],
  cs[cs$model == "L1", c("term", "odds_ratio", "or_lo", "or_hi", "p_value")],
  by = "term", suffixes = c("_survey", "_llm"))
drivers <- drivers[order(-abs(log(drivers$odds_ratio_llm))), ]
n_shared <- sum(grepl("^(reason_grp|conformance_status)", drivers$term))
cat(sprintf("\n  survey-vs-LLM drivers: %d shared terms, %d of them rule/reason\n",
            nrow(drivers), n_shared))
stopifnot(n_shared >= 8)

# ──────────────────────────────────────────────────────────────────── write out
sm <- do.call(rbind, summaries)
write.csv(sm, file.path(OUTDIR, "model_summary.csv"), row.names = FALSE)
write.csv(cs, file.path(OUTDIR, "coefficients.csv"), row.names = FALSE)
write.csv(blocks, file.path(OUTDIR, "block_contributions.csv"), row.names = FALSE)
write.csv(type2, file.path(OUTDIR, "type2_tests.csv"), row.names = FALSE)
write.csv(vifs, file.path(OUTDIR, "vif.csv"), row.names = FALSE)
write.csv(po_check, file.path(OUTDIR, "proportional_odds_check.csv"), row.names = FALSE)
write.csv(perm, file.path(OUTDIR, "permutation_null.csv"), row.names = FALSE)
write.csv(calib, file.path(OUTDIR, "calibration.csv"), row.names = FALSE)
write.csv(drivers, file.path(OUTDIR, "survey_vs_llm_drivers.csv"), row.names = FALSE)

roc_s1 <- pROC::roc(A$survey_not_easy, fitted(S1), quiet = TRUE)
roc_s2 <- pROC::roc(A$survey_not_easy, fitted(S2), quiet = TRUE)
roc_df <- rbind(
  data.frame(model = "S1", fpr = 1 - roc_s1$specificities, tpr = roc_s1$sensitivities),
  data.frame(model = "S2", fpr = 1 - roc_s2$specificities, tpr = roc_s2$sensitivities))
write.csv(roc_df, file.path(OUTDIR, "roc_curves.csv"), row.names = FALSE)

payload <- list(
  meta = list(
    r_version = as.character(getRversion()),
    n_analysis = nrow(A), n_rules = nrow(R), n_weighted = nrow(W),
    events_not_easy = sum(A$survey_not_easy), events_hard = sum(A$survey_hard),
    base_rate_not_easy = mean(A$survey_not_easy),
    base_rate_hard = mean(A$survey_hard),
    llm_high_rate = mean(A$llm_high, na.rm = TRUE),
    vif_high = nhigh,
    po_median_spread = median(po_check$spread, na.rm = TRUE),
    repeat_corpus = mean(d$repeat_contact_obs == "yes", na.rm = TRUE),
    repeat_respondents = mean(A$repeat_contact_obs == "yes")),
  summary = sm, blocks = blocks, type2 = type2, perm = perm,
  calibration = calib, drivers = head(drivers, 25),
  coefficients = cs, vif = vifs, po_check = po_check)
write(toJSON(payload, dataframe = "rows", auto_unbox = TRUE, na = "null", digits = 6),
      file.path(OUTDIR, "model_results.json"))

cat(sprintf("\nwrote %s\n", file.path(OUTDIR, "model_results.json")))
cat("  9 CSVs + JSON\n")
