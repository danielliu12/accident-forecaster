"""
Run the county-based forecaster end to end.

    python run.py --hours 48

Outputs (./output):
  county_risk.csv     all 92 counties, scored for the horizon
  county_targets.csv  top counties formatted for Google Ads county targeting
  budget_shares.csv   blended metro shares vs Phase 2 static
  cluster_mix.csv     keyword cluster mix per metro
  dayparting.csv      high-risk hours + suggested bid adjustments
  risk_map.html       interactive map of dynamic-tier counties
"""
from __future__ import annotations

import argparse
import os

import config
import deploy
import geo
import mapbuild
import memory
import model
import sources


def run(hours: int = 48, outdir: str = "output"):
    os.makedirs(outdir, exist_ok=True)
    print("Loading county opportunity table ...")
    counties = sources.load_counties()
    print("Fetching weather for %d dynamic counties ..." % config.DYNAMIC_N)
    weather = sources.fetch_weather(hours)
    print("Fetching live incidents ...")
    incidents, live_events = sources.fetch_incidents()
    hist = memory.load()
    hist = memory.update(hist, live_events)
    memory.save(hist)
    live_ids = {memory.event_id(e) for e in live_events}
    trail = memory.trailing(hist, live_ids)
    trailing_scores = memory.county_trailing_scores(trail)
    if trail:
        print(f"  {len(trail)} trailing incident(s) in memory "
              f"(top: {trail[0]['type']} in {trail[0]['county']}, "
              f"{trail[0]['age_h']:.0f}h ago, importance "
              f"{trail[0]['importance']:.2f})")

    scores, hourly = model.score(counties, weather, incidents, hours,
                                 trailing_scores)
    print("Fetching county boundaries ...")
    geodata = geo.fetch_indiana_geojson()
    print("Fetching commuter origin-destination data (Census LODES; "
          "~1-2 min first run) ...")
    flows = geo.fetch_flows()
    origins = geo.top_origins(flows, geodata)
    prio, eff = deploy.load_phase2()
    shares = deploy.budget_shares(scores)
    targets = deploy.county_targets(scores)
    mix = deploy.cluster_mix(eff)
    parts = deploy.daypart(hourly, scores)

    scores.to_csv(f"{outdir}/county_risk.csv", index=False)
    targets.to_csv(f"{outdir}/county_targets.csv", index=False)
    shares.to_csv(f"{outdir}/budget_shares.csv", index=False)
    mix.to_csv(f"{outdir}/cluster_mix.csv", index=False)
    parts.to_csv(f"{outdir}/dayparting.csv", index=False)
    mapbuild.build_map(scores, geodata, origins, f"{outdir}/risk_map.html",
                       hours, trail)

    print("\n=== Blended budget shares (next %d h) ===" % hours)
    print(shares.to_string(index=False))
    print("\n=== Top 10 counties ===")
    print(targets.head(10).to_string(index=False))
    print(f"\nOutputs written to ./{outdir} (open risk_map.html).")
    return scores, shares, targets, mix, parts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=48)
    args = ap.parse_args()
    run(args.hours)
