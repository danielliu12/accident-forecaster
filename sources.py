"""
Data connectors (v2): county opportunity table, batched Open-Meteo
forecasts for the dynamic counties, 511/CARS live incidents.

All network connectors degrade gracefully to neutral values so a
scheduled run always completes.
"""
from __future__ import annotations

import datetime as dt
import math
import sys

import pandas as pd
import requests

import config


def load_counties() -> pd.DataFrame:
    df = pd.read_csv(config.COUNTY_CSV)
    df["county"] = df["county"].astype(str).str.strip()
    df["dynamic"] = False
    dyn = df.nlargest(config.DYNAMIC_N, "opportunity_score")["county"]
    df.loc[df["county"].isin(dyn), "dynamic"] = True
    df["metro"] = df["county"].map(config.COUNTY_TO_METRO).fillna("other_in")
    return df


# ---------------------------------------------------------------------------
# Weather — one batched request for all dynamic counties
# ---------------------------------------------------------------------------
HOURLY_VARS = ["precipitation", "snowfall", "temperature_2m", "visibility",
               "wind_gusts_10m", "is_day", "weather_code"]


def fetch_weather(hours: int = 48) -> dict[str, pd.DataFrame]:
    names = list(config.COUNTY_CENTROIDS)
    lats = ",".join(str(config.COUNTY_CENTROIDS[n][0]) for n in names)
    lons = ",".join(str(config.COUNTY_CENTROIDS[n][1]) for n in names)
    params = {
        "latitude": lats, "longitude": lons,
        "hourly": ",".join(HOURLY_VARS),
        "forecast_days": min(7, max(1, math.ceil(hours / 24))),
        "timezone": "America/Indiana/Indianapolis",
    }
    out = {}
    try:
        r = requests.get(config.OPEN_METEO_URL, params=params, timeout=30)
        r.raise_for_status()
        payload = r.json()
        if isinstance(payload, dict):  # single-location fallback
            payload = [payload]
        for name, loc in zip(names, payload):
            df = pd.DataFrame(loc["hourly"])
            df["time"] = pd.to_datetime(df["time"])
            df = df.set_index("time").iloc[:hours]
            df["freezing_precip_flag"] = df["weather_code"].isin(
                [56, 57, 66, 67])
            out[name] = df
    except Exception as e:  # noqa: BLE001
        print(f"[warn] weather fetch failed ({e}); using neutral weather.",
              file=sys.stderr)
    for name in names:  # fill any gaps
        out.setdefault(name, neutral_weather(hours))
    return out


def neutral_weather(hours: int) -> pd.DataFrame:
    idx = pd.date_range(dt.datetime.now().replace(minute=0, second=0,
                                                  microsecond=0),
                        periods=hours, freq="h")
    return pd.DataFrame({
        "precipitation": 0.0, "snowfall": 0.0, "temperature_2m": 15.0,
        "visibility": 20000.0, "wind_gusts_10m": 10.0, "is_day": 1,
        "weather_code": 0, "freezing_precip_flag": False,
    }, index=idx)


def weather_multiplier(row: pd.Series) -> float:
    m = config.WEATHER_MULTIPLIERS
    mult = 1.0
    snow = row.get("snowfall", 0.0)        # cm/h
    rain = row.get("precipitation", 0.0)   # mm/h
    if row.get("freezing_precip_flag", False) or (
            rain > 0.1 and row.get("temperature_2m", 15) <= 0):
        mult *= m["freezing_precip"]
    elif snow > 2.5:
        mult *= m["snow_heavy"]
    elif snow > 1.0:
        mult *= m["snow_moderate"]
    elif snow > 0.1:
        mult *= m["snow_light"]
    elif rain > 7.6:
        mult *= m["rain_heavy"]
    elif rain > 2.5:
        mult *= m["rain_moderate"]
    elif rain > 0.1:
        mult *= m["rain_light"]
    if row.get("visibility", 20000) < 1000:
        mult *= m["fog"]
    if not row.get("is_day", 1):
        mult *= m["darkness"]
    if row.get("wind_gusts_10m", 0) > 40:
        mult *= m["high_wind"]
    return min(mult, config.MAX_MULTIPLIER)


# ---------------------------------------------------------------------------
# Live incidents -> per-county active event counts
# ---------------------------------------------------------------------------
def fetch_incidents() -> tuple[pd.Series, list[dict]]:
    """(county -> active event count, event-level list with lat/lon/type/
    county). Events are assigned to the nearest dynamic-county centroid
    within ~35 km; others are dropped."""
    counts = {n: 0 for n in config.COUNTY_CENTROIDS}
    events: list[dict] = []
    items = None
    for url in config.TRAFFICWISE_EVENTS_URLS:
        if config.TRAFFICWISE_API_KEY and "api/v2" in url:
            url += "&key=" + config.TRAFFICWISE_API_KEY
        try:
            r = requests.get(url, timeout=20,
                             headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            raw = r.json()
            items = raw if isinstance(raw, list) else raw.get("events", [])
            break
        except Exception as e:  # noqa: BLE001
            print(f"[warn] event feed failed: {url.split('?')[0]} ({e})",
                  file=sys.stderr)
    try:
        if items is None:
            raise RuntimeError("all event feeds unavailable")
        for ev in items:
            lat = (ev.get("latitude") or ev.get("lat")
                   or ev.get("Latitude"))
            lon = (ev.get("longitude") or ev.get("lon")
                   or ev.get("Longitude"))
            if lat is None or lon is None:
                continue
            lat, lon = float(lat), float(lon)
            best, bd = None, 0.35  # ~35 km cap in degrees
            for name, (cla, clo) in config.COUNTY_CENTROIDS.items():
                d = math.hypot(lat - cla, lon - clo)
                if d < bd:
                    best, bd = name, d
            if best:
                counts[best] += 1
                etype = str(ev.get("type") or ev.get("EventType")
                            or "event")
                sub = ev.get("Subtype") or ev.get("EventSubType") or ""
                desc = ev.get("Description") or ""
                events.append({
                    "id": ev.get("id") or ev.get("ID"),
                    "lat": lat, "lon": lon,
                    "type": f"{etype} {sub}".strip(),
                    "desc": str(desc)[:160], "county": best,
                    "severity": ev.get("Severity"),
                    "full_closure": bool(ev.get("IsFullClosure")),
                })
    except Exception as e:  # noqa: BLE001
        print(f"[warn] incident feed unavailable: {e}", file=sys.stderr)
    return pd.Series(counts), events
