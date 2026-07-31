"""
Geometry + commuter-flow data (fetched live in Colab; graceful fallbacks).

- Indiana county polygons: Census/plotly counties GeoJSON, filtered to
  STATE == "18". Gives real boundaries for the choropleth and centroids
  computed from the polygons (replacing hand-entered centroids for flows).
- Commuter origins: Census LODES8 origin-destination files for Indiana
  (block-level home->work job counts, aggregated to county). The inbound
  commuter mix of a county is the best public proxy for "where the people
  driving through it come from." main = both ends in Indiana; aux adds
  out-of-state residents working in Indiana (rolled up to state level).
"""
from __future__ import annotations

import re
import sys

import pandas as pd
import requests

GEOJSON_URL = ("https://raw.githubusercontent.com/plotly/datasets/master/"
               "geojson-counties-fips.json")
LODES_MAIN = ("https://lehd.ces.census.gov/data/lodes/LODES8/in/od/"
              "in_od_main_JT00_2022.csv.gz")
LODES_AUX = ("https://lehd.ces.census.gov/data/lodes/LODES8/in/od/"
             "in_od_aux_JT00_2022.csv.gz")

NEIGHBOR_STATES = {  # state FIPS -> (label, approx centroid) for flow lines
    "17": ("Illinois", (40.0, -89.2)), "21": ("Kentucky", (37.5, -85.3)),
    "39": ("Ohio", (40.3, -82.8)), "26": ("Michigan", (43.3, -84.6)),
}
STATE_NAMES = {"17": "Illinois", "21": "Kentucky", "39": "Ohio",
               "26": "Michigan", "state": "out of state"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", str(s).lower())


def fetch_indiana_geojson() -> dict | None:
    """{'features': [...], 'fips_to_name': {}, 'name_to_fips': {},
        'centroids': {fips: (lat, lon)}} or None if unreachable."""
    try:
        gj = requests.get(GEOJSON_URL, timeout=90).json()
    except Exception as e:  # noqa: BLE001
        print(f"[warn] county GeoJSON unavailable ({e}); map falls back "
              "to geographic circles.", file=sys.stderr)
        return None
    feats = [f for f in gj["features"]
             if f.get("properties", {}).get("STATE") == "18"]
    fips_to_name, centroids = {}, {}
    for f in feats:
        fips = f.get("id") or ("18" + f["properties"]["COUNTY"])
        f["id"] = fips
        name = f["properties"].get("NAME", fips)
        fips_to_name[fips] = name
        centroids[fips] = _centroid(f["geometry"])
    return {"features": feats, "fips_to_name": fips_to_name,
            "name_to_fips": {_norm(v): k for k, v in fips_to_name.items()},
            "centroids": centroids}


def _centroid(geom: dict) -> tuple[float, float]:
    if geom["type"] == "Polygon":
        ring = geom["coordinates"][0]
    else:  # MultiPolygon: use largest ring
        ring = max((p[0] for p in geom["coordinates"]), key=len)
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    return (round(lat, 4), round(lon, 4))


def fetch_flows() -> pd.DataFrame | None:
    """County-level OD: columns w_cty (workplace FIPS, all 18xxx),
    h_cty (home FIPS, any state), jobs. None if unreachable."""
    frames = []
    for url in (LODES_MAIN, LODES_AUX):
        try:
            df = pd.read_csv(url, usecols=["w_geocode", "h_geocode", "S000"],
                             dtype={"w_geocode": str, "h_geocode": str})
            frames.append(df)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] LODES fetch failed for {url.split('/')[-1]} "
                  f"({e})", file=sys.stderr)
    if not frames:
        return None
    od = pd.concat(frames, ignore_index=True)
    od["w_cty"] = od["w_geocode"].str[:5]
    od["h_cty"] = od["h_geocode"].str[:5]
    return (od.groupby(["w_cty", "h_cty"])["S000"].sum()
            .rename("jobs").reset_index())


def top_origins(flows: pd.DataFrame | None, geo: dict | None,
                k: int = 6) -> dict:
    """{workplace_fips: [{label, share, lat, lon(or None)}...]} — the top
    inbound commuter origins for every Indiana county."""
    if flows is None:
        return {}
    fips_to_name = geo["fips_to_name"] if geo else {}
    centroids = geo["centroids"] if geo else {}
    out = {}
    for w, grp in flows.groupby("w_cty"):
        total = grp["jobs"].sum()
        ext = grp[grp["h_cty"] != w].copy()
        # roll out-of-state homes up to state level
        ext["origin"] = ext["h_cty"].where(
            ext["h_cty"].str.startswith("18"), "S" + ext["h_cty"].str[:2])
        agg = (ext.groupby("origin")["jobs"].sum()
               .sort_values(ascending=False).head(k))
        rows = []
        for origin, jobs in agg.items():
            if origin.startswith("S"):
                sf = origin[1:]
                label, cen = NEIGHBOR_STATES.get(
                    sf, (STATE_NAMES.get(sf, f"state {sf}"), None))
            else:
                label = fips_to_name.get(origin, origin) + " Co."
                cen = centroids.get(origin)
            rows.append({
                "label": label, "share": round(float(jobs / total), 3),
                "lat": cen[0] if cen else None,
                "lon": cen[1] if cen else None,
            })
        internal = float(grp[grp["h_cty"] == w]["jobs"].sum() / total)
        out[w] = {"origins": rows, "internal_share": round(internal, 3)}
    return out
