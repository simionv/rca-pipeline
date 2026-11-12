"""Measure customer effort from the shape of the interaction. No LLM, no cost.

Run with the project venv:

    .venv/Scripts/python.exe scripts/build_effort_features.py

Writes runs/intermediate/csd_effort_features.csv for ALL 2026 incidents.

What this is
------------
The LLM reads the transcript and judges effort. This script measures the things
the interaction records exactly: how many turns it took, how many agents touched
it, how long the customer waited, and whether they had been here before. The two
are independent readings of the same interaction, which is what makes the
comparison in notebook 09 worth anything.

Every column is prefixed `obs_` so it can never collide with an LLM field, and
so `drop_enrichment_cols()` cannot mistake it for stale enrichment.

Honest limits, carried into the output
--------------------------------------
* `CONTACT_ID` is only populated on customer-authored entries, so ~13% of
  incidents have no resolvable contact. Those get `obs_repeat_contact = <NA>`,
  never False - "we do not know" and "no" are different facts.
* Channel never varies within an incident in this corpus (verified: 0 of 56,935),
  so there is no channel-switch feature here. `obs_channel` is the incident's
  single channel, for segmentation only.
* `obs_effort_index` is an authored equal-weight composite, not a fitted model.
  There is nothing to fit against until survey data arrives. Its components are
  all published so it can be reweighted rather than rebuilt.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ModuleNotFoundError as exc:                                   # pragma: no cover
    sys.exit(f"{exc}. Run this with the project venv:\n"
             r"    .venv\Scripts\python.exe scripts\build_effort_features.py")

if not pd.__version__.startswith("3."):
    sys.exit(f"pandas {pd.__version__}; expected 3.x from .venv. Wrong interpreter?")

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "scopus content"
THREADS = DATA / "scopus content_2026_threads.tsv"
META = DATA / "scopus content_2026_metadata.tsv"
OUT = BASE / "runs" / "intermediate" / "csd_effort_features.csv"

ID = "INCIDENT_REF"
CUSTOMER_TYPES = ("Customer", "Customer Proxy")
STAFF_TYPE = "Staff Account"
PRIOR_WINDOW_DAYS = 90

# The four components of obs_effort_index, equal-weighted after percentile ranking.
INDEX_PARTS = ["obs_customer_turns", "obs_agent_handoffs", "obs_span_h", "obs_repeat_contact"]


def main() -> None:
    print("Loading threads...")
    t = pd.read_csv(THREADS, sep="\t", dtype=str)
    t["dt"] = pd.to_datetime(t["DATE_CREATED"], errors="coerce")
    t[ID] = t[ID].astype(str).str.strip()
    print(f"  {len(t):,} entries across {t[ID].nunique():,} incidents")
    assert t["dt"].notna().all(), "some thread entries have an unparseable DATE_CREATED"

    is_cust = t["THREAD_ENTRY_TYPE"].isin(CUSTOMER_TYPES)
    is_staff = t["THREAD_ENTRY_TYPE"] == STAFF_TYPE

    # ── per-incident counts and timings ──────────────────────────────────
    g = t.groupby(ID)
    f = pd.DataFrame({
        "obs_turns": g.size(),
        "obs_distinct_agents": g["AGENT_ID"].nunique(dropna=True),
        "obs_channel": g["INCIDENT_CHANNEL"].first(),
        "_t_first": g["dt"].min(),
        "_t_last": g["dt"].max(),
    })
    f["obs_customer_turns"] = t[is_cust].groupby(ID).size().reindex(f.index).fillna(0).astype(int)
    f["obs_agent_turns"] = t[is_staff].groupby(ID).size().reindex(f.index).fillna(0).astype(int)

    # An agent handoff is a SECOND distinct agent, so a normal single-owner
    # ticket scores zero rather than one.
    f["obs_agent_handoffs"] = (f["obs_distinct_agents"] - 1).clip(lower=0)
    f["obs_span_h"] = (f["_t_last"] - f["_t_first"]).dt.total_seconds() / 3600

    # ── time to the first staff reply after the first customer message ──
    first_cust = t[is_cust].groupby(ID)["dt"].min()
    staff = t[is_staff][[ID, "dt"]].join(first_cust.rename("_c0"), on=ID)
    after = staff[staff["dt"] >= staff["_c0"]]
    first_reply = after.groupby(ID)["dt"].min()
    f["obs_first_response_h"] = (
        (first_reply - first_cust).dt.total_seconds() / 3600).reindex(f.index)

    # ── repeat contact ───────────────────────────────────────────────────
    # CONTACT_ID appears only on customer-authored entries. Where an incident has
    # none, the customer is unknown and repeat status is unknowable - recorded as
    # NA, not False.
    contact = (t[is_cust].dropna(subset=["CONTACT_ID"])
               .groupby(ID)["CONTACT_ID"].first())
    f["obs_contact_id"] = contact.reindex(f.index)
    known = f["obs_contact_id"].notna()
    n_tickets = f.loc[known].groupby("obs_contact_id").size()
    f["obs_contact_ticket_count"] = f["obs_contact_id"].map(n_tickets)
    f["obs_repeat_contact"] = pd.Series(
        np.where(known, f["obs_contact_ticket_count"] > 1, None),
        index=f.index, dtype="boolean")
    print(f"  contact resolvable for {known.mean():.1%} of incidents; "
          f"repeat rate among those {f.loc[known, 'obs_repeat_contact'].mean():.1%}")

    # ── prior tickets from the same contact in the preceding 90 days ────
    known_df = (f.loc[known, ["obs_contact_id", "_t_first"]]
                .reset_index().sort_values(["obs_contact_id", "_t_first"]))
    prior = []
    for _, grp in known_df.groupby("obs_contact_id", sort=False):
        times = grp["_t_first"].to_numpy()
        cutoff = times - np.timedelta64(PRIOR_WINDOW_DAYS, "D")
        # times is sorted, so the count of earlier tickets still inside the
        # window is a pair of binary searches - O(n log n) rather than O(n^2).
        starts = np.searchsorted(times, cutoff, side="left")
        prior.append(pd.Series(np.arange(len(times)) - starts, index=grp[ID]))
    f["obs_prior_tickets_90d"] = (pd.concat(prior).reindex(f.index)
                                  if prior else pd.Series(index=f.index, dtype="float"))
    print(f"  incidents with a prior ticket from the same contact in {PRIOR_WINDOW_DAYS}d: "
          f"{(f['obs_prior_tickets_90d'] > 0).sum():,}")

    # ── metadata ─────────────────────────────────────────────────────────
    m = pd.read_csv(META, sep="\t", dtype=str,
                    usecols=["incident_reference", "number_of_responses"])
    m["incident_reference"] = m["incident_reference"].astype(str).str.strip()
    f["obs_responses"] = pd.to_numeric(
        m.set_index("incident_reference")["number_of_responses"].reindex(f.index),
        errors="coerce")

    # ── composite index ──────────────────────────────────────────────────
    # Percentile-rank each component, then average the components that exist for
    # that row. Averaging over present components (rather than filling nulls with
    # zero) stops the ~13% with unknown repeat status from being scored as if we
    # had confirmed they were first-time contacts.
    ranks = pd.DataFrame(index=f.index)
    for col in INDEX_PARTS:
        s = f[col]
        s = s.astype("float") if s.dtype.name == "boolean" else pd.to_numeric(s, errors="coerce")
        ranks[col] = s.rank(pct=True, na_option="keep")
    f["obs_effort_index"] = ranks.mean(axis=1, skipna=True).round(4)
    f["obs_index_components"] = ranks.notna().sum(axis=1)
    assert f["obs_effort_index"].between(0, 1).all(), "index escaped [0, 1]"
    assert (f["obs_index_components"] > 0).all(), "an incident has no index components"

    out = f.drop(columns=["_t_first", "_t_last", "obs_contact_id"]).reset_index()
    out["obs_span_h"] = out["obs_span_h"].round(2)
    out["obs_first_response_h"] = out["obs_first_response_h"].round(2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"\nWrote {OUT.relative_to(BASE)}  ({len(out):,} incidents x {len(out.columns)} cols)")

    print("\nDistributions:")
    desc = out[["obs_turns", "obs_customer_turns", "obs_agent_handoffs",
                "obs_first_response_h", "obs_span_h", "obs_prior_tickets_90d",
                "obs_effort_index"]].describe(percentiles=[0.25, 0.5, 0.75, 0.9]).T
    print(desc.to_string(float_format=lambda v: f"{v:,.2f}"))
    print(f"\nobs_repeat_contact: True {int((out.obs_repeat_contact == True).sum()):,}  "
          f"False {int((out.obs_repeat_contact == False).sum()):,}  "
          f"unknown {int(out.obs_repeat_contact.isna().sum()):,}")
    print("\nNote: only "
          f"{(out.obs_customer_turns > 1).mean():.1%} of incidents have more than one customer "
          "turn, so the observed signals are less dispersed than a multi-turn corpus would give.")


if __name__ == "__main__":
    main()
