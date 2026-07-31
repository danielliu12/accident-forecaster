"""
County risk model (v2).

risk(county, hour) = opportunity(county) × exposure(hour-of-week)
                     × weather_multiplier(county, hour)
county_score       = Σ_hours risk × incident_boost(county)

Static-tier counties (outside the top DYNAMIC_N) use neutral weather, so
their score is pure baseline — they can't gain from conditions but remain
in the allocation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config
from sources import weather_multiplier


def hourly_exposure() -> np.ndarray:
    vec = []
    for wd in range(7):
        prof = config.WEEKDAY_HOURLY if wd < 5 else config.WEEKEND_HOURLY
        vec.extend(prof)
    v = np.array(vec, dtype=float)
    return v / v.mean()


def score(counties: pd.DataFrame,
          weather: dict[str, pd.DataFrame],
          incidents: pd.Series,
          hours: int = 48,
          trailing_scores: dict[str, float] | None = None
          ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (county_scores, county_hourly)."""
    exposure = hourly_exposure()
    hourly_rows = []
    horizon, drivers = {}, {}
    for _, c in counties.iterrows():
        name = c["county"]
        wdf = weather.get(name)
        if c["dynamic"] and wdf is not None:
            total = 0.0
            cond_hours: dict[str, int] = {}
            peak_ts, peak_risk = None, -1.0
            for ts, row in wdf.iloc[:hours].iterrows():
                wm = weather_multiplier(row)
                ex = float(exposure[ts.weekday() * 24 + ts.hour])
                risk = wm * ex
                total += risk
                lab = condition_label(row)
                if lab:
                    cond_hours[lab] = cond_hours.get(lab, 0) + 1
                if risk > peak_risk:
                    peak_risk, peak_ts = risk, ts
                hourly_rows.append({
                    "county": name, "time": ts,
                    "weather_mult": round(wm, 3), "exposure": round(ex, 3),
                    "hour_risk": round(risk, 3),
                })
            horizon[name] = total
            cond_txt = ", ".join(f"{v}h {k}" for k, v in sorted(
                cond_hours.items(), key=lambda x: -x[1])) or "clear/dry"
            drivers[name] = {
                "conditions": cond_txt,
                "peak": peak_ts.strftime("%a %H:00") if peak_ts is not None
                        else "",
            }
        else:
            horizon[name] = float(hours)  # neutral: mean multiplier 1.0

    out = counties.copy()
    out["horizon_weather"] = out["county"].map(horizon)
    out["wx_conditions"] = out["county"].map(
        lambda n: drivers.get(n, {}).get("conditions", "static tier"))
    out["wx_peak"] = out["county"].map(
        lambda n: drivers.get(n, {}).get("peak", ""))
    out["weather_lift"] = (out["horizon_weather"] / hours).round(3)
    ev = out["county"].map(incidents).fillna(0)
    out["active_events"] = ev.astype(int)
    tr = out["county"].map(trailing_scores or {}).fillna(0.0)
    out["trailing_weight"] = tr.round(2)
    out["incident_boost"] = np.minimum(
        1 + config.INCIDENT_BOOST_PER_EVENT * ev
        + config.TRAILING_BOOST_PER_POINT * tr,
        config.INCIDENT_BOOST_CAP)
    out["risk_score"] = (out["opportunity_score"] * out["horizon_weather"]
                         * out["incident_boost"])
    out["risk_score"] = (100 * out["risk_score"]
                         / out["risk_score"].max()).round(2)
    out = out.sort_values("risk_score", ascending=False)
    return out, pd.DataFrame(hourly_rows)


def condition_label(row) -> str | None:
    """Human label for the dominant adverse condition in a forecast hour."""
    rain = row.get("precipitation", 0.0)
    snow = row.get("snowfall", 0.0)
    if row.get("freezing_precip_flag", False) or (
            rain > 0.1 and row.get("temperature_2m", 15) <= 0):
        return "freezing rain/ice"
    if snow > 1.0:
        return "heavy snow"
    if snow > 0.1:
        return "snow"
    if rain > 2.5:
        return "heavy rain"
    if rain > 0.1:
        return "rain"
    if row.get("visibility", 20000) < 1000:
        return "fog"
    return None
