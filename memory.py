"""
Trailing-incident memory.

Every run logs the live 511 events it observes. Events that have dropped
off the live feed become "trailing": their importance decays as

    importance = magnitude * 0.5 ** (hours_since_last_seen / HALF_LIFE_H)

so a magnitude-5 pileup from 3 days ago still registers (~0.35 of its
original weight at the default 48 h half-life) while minor events fade
fast. Trailing weight boosts county risk at half the per-point strength
of a live event and is drawn on the map as fading markers.

Persistence: JSON file. In Colab, mount Google Drive to keep memory
across sessions; otherwise memory covers the current session only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

import config

MAGNITUDE_KEYWORDS = [
    ("pileup", 5), ("multi vehicle", 5), ("multi-vehicle", 5),
    ("closed", 4), ("closure", 4), ("hazmat", 4), ("spill", 4),
    ("overturned", 4), ("jackknif", 4),
    ("crash", 3), ("accident", 3), ("collision", 3),
    ("lane blocked", 2), ("lane closed", 2), ("restriction", 2),
    ("stalled", 1), ("disabled", 1), ("construction", 1),
]
DEFAULT_MAGNITUDE = 2


def magnitude_of(event_type: str, desc: str = "", severity=None,
                 full_closure: bool = False) -> int:
    t = f"{event_type} {desc}".lower()
    mag = DEFAULT_MAGNITUDE
    for kw, m in MAGNITUDE_KEYWORDS:
        if kw in t:
            mag = m
            break
    if full_closure:
        mag = max(mag, 4)
    try:  # Castle Rock Severity is often "1".."5"
        mag = max(mag, min(int(severity), 5))
    except (TypeError, ValueError):
        pass
    return mag


def event_id(ev: dict) -> str:
    raw = ev.get("id") or f'{ev.get("lat"):.3f}|{ev.get("lon"):.3f}|' \
                          f'{ev.get("type", "")}'
    return hashlib.md5(str(raw).encode()).hexdigest()[:12]


def history_path() -> str:
    envp = os.environ.get("HISTORY_PATH")
    if envp:
        return envp
    drive = "/content/drive/MyDrive/accident_forecaster"
    if os.path.isdir("/content/drive/MyDrive"):
        os.makedirs(drive, exist_ok=True)
        return f"{drive}/incident_history.json"
    return "incident_history.json"


def load() -> dict:
    """Local history, merged with the machine-built archive from the
    GitHub Actions poller when config.INCIDENT_LOG_URL is set. The remote
    archive wins for events it knows about (its last_seen is fresher)."""
    hist = {}
    try:
        with open(history_path()) as f:
            hist = json.load(f)
    except Exception:  # noqa: BLE001
        pass
    if config.INCIDENT_LOG_URL:
        try:
            import requests
            remote = requests.get(config.INCIDENT_LOG_URL, timeout=30).json()
            for eid, e in remote.items():
                if (eid not in hist
                        or e["last_seen"] >= hist[eid]["last_seen"]):
                    hist[eid] = e
            print(f"[info] merged {len(remote)} events from remote archive")
        except Exception as e:  # noqa: BLE001
            print(f"[warn] remote incident archive unavailable: {e}")
    return hist


def save(hist: dict) -> None:
    with open(history_path(), "w") as f:
        json.dump(hist, f)


def update(hist: dict, live_events: list[dict],
           now: dt.datetime | None = None) -> dict:
    """Merge this run's live events into history; prune fully-faded ones."""
    now = now or dt.datetime.now()
    now_s = now.isoformat(timespec="seconds")
    live_ids = set()
    for ev in live_events:
        eid = event_id(ev)
        live_ids.add(eid)
        if eid in hist:
            hist[eid]["last_seen"] = now_s
        else:
            hist[eid] = {
                "first_seen": now_s, "last_seen": now_s,
                "lat": ev.get("lat"), "lon": ev.get("lon"),
                "county": ev.get("county"), "type": ev.get("type", "event"),
                "desc": ev.get("desc", ""),
                "magnitude": magnitude_of(ev.get("type", ""),
                                          ev.get("desc", ""),
                                          ev.get("severity"),
                                          ev.get("full_closure", False)),
            }
    # prune events decayed below 5% of a magnitude-1 event
    keep = {}
    for eid, e in hist.items():
        if eid in live_ids or _decay(e, now) * e["magnitude"] >= 0.05:
            keep[eid] = e
    return keep


def _decay(e: dict, now: dt.datetime) -> float:
    last = dt.datetime.fromisoformat(e["last_seen"])
    hours = max((now - last).total_seconds() / 3600, 0)
    return 0.5 ** (hours / config.TRAILING_HALF_LIFE_H)


def trailing(hist: dict, live_ids: set[str],
             now: dt.datetime | None = None) -> list[dict]:
    """Decayed non-live events: [{lat, lon, county, type, magnitude,
    importance, age_h}] with importance = magnitude * decay."""
    now = now or dt.datetime.now()
    out = []
    for eid, e in hist.items():
        if eid in live_ids:
            continue
        d = _decay(e, now)
        imp = e["magnitude"] * d
        if imp < 0.05:
            continue
        age_h = (now - dt.datetime.fromisoformat(e["last_seen"])
                 ).total_seconds() / 3600
        out.append({**e, "importance": round(imp, 3),
                    "decay": round(d, 3), "age_h": round(age_h, 1)})
    return sorted(out, key=lambda x: -x["importance"])


def county_trailing_scores(trail: list[dict]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for e in trail:
        c = e.get("county")
        if c:
            scores[c] = scores.get(c, 0.0) + e["importance"]
    return scores
