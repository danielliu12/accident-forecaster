# Indiana Accident Risk Forecaster v3 (county choropleth + flows + live) → Ad Plan

Baseline layer: EMS-derived motor-vehicle injury opportunity by county
(Indiana Data Hub EMS incidents, severity-weighted) — replaces the
discontinued ARIES/MPH crash extract. Live layers: Open-Meteo hourly
weather for the top-25 opportunity counties (~84% of statewide
opportunity) and INDOT/511 active incidents.

risk(county) = EMS opportunity × hour-of-week exposure × weather
multiplier (rain/snow/ice/fog/darkness/wind, literature-anchored,
capped 3.5×) × incident boost (+10%/event, capped 1.5×).

Outputs: blended metro budget shares (Phase 2 static anchor, forecast may
shift up to 35%), county_targets.csv formatted for Google Ads *county*
location targeting, dayparting bid adjustments, per-metro keyword cluster
mix from Phase 2 CPC efficiency, interactive risk map.

Normal usage: open forecaster_colab.ipynb in Google Colab → Runtime →
Run all. No editing required. Local usage: `pip install pandas numpy
requests` then `python run.py --hours 48`.

Compliance: targets geographic conditions only, never individuals — no
victim identification or incident-specific retargeting (Indiana Prof.
Cond. R. 7.1–7.3 advertising vs solicitation line). Keep creative
condition-aware, not incident-specific.

Upgrade paths: (1) export the EMS logs' vehicle-accident runs with a
timestamp column to learn the real hour-of-week curve; (2) with ZIP-level
EMS aggregation, drop below county to ZIP targeting; (3) verify/refresh
the 511 feed URL in config.py if the incident layer reports unavailable.

## v3 additions
- County-polygon choropleth (Census/plotly GeoJSON) — zoom-correct
  geometry; meter-based circle fallback if the boundary fetch fails.
- Hover reasoning per county: EMS opportunity rank + injured/yr, horizon
  weather conditions + peak-risk window, active incidents, top inbound
  commuter origins.
- Click-to-draw commuter inflow lines from Census LODES8 OD data (main +
  aux), county-aggregated; out-of-state origins rolled up to state level.
- Live mode: the map re-fetches Open-Meteo in-browser every 15 min and
  recolors itself while open. Incidents refresh on notebook re-run. For a
  permanently hosted always-updating URL, run this on a schedule (GitHub
  Actions cron -> GitHub Pages).

## v4 additions — trailing incidents
Past incidents keep influencing county risk: importance = magnitude ×
0.5^(hours/48). Magnitude 1-5 from event type/severity/closure status
(pileup/closure=4-5, crash=3, lane restriction=2, stalled=1). Boost:
+10%/live event +5%/trailing point, capped ×1.75. Fading orange map
markers, opacity = decay. Memory persists via Google Drive (Colab) or —
better — via the GitHub Actions poller (GITHUB_SETUP.md), which polls
511 every 20 min, builds the archive machine-independently, and publishes
an always-live map to GitHub Pages. Note: INDOT publishes no historical
incident archive (unlike e.g. NY), hence the self-built archive.
