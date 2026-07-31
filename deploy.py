"""
Configuration — Indiana Accident Forecaster v2 (county-based).

Spatial unit: county. The baseline layer is EMS-derived motor-vehicle
injury opportunity (data/county_opportunity.csv, built from Indiana Data
Hub EMS incidents with severity weighting). The top DYNAMIC_N counties by
opportunity get live weather + incident monitoring; the long tail stays at
its static baseline.
"""

COUNTY_CSV = "data/county_opportunity.csv"
PHASE2_PRIORITY_CSV = "data/phase2_metro_priority.csv"
PHASE2_EFFICIENCY_CSV = "data/phase2_cluster_metro_efficiency.csv"

DYNAMIC_N = 25  # counties with live weather/incidents (~84% of opportunity)

# Approximate county centroids for the dynamic tier (lat, lon). Used only
# for weather sampling and nearest-county incident assignment; ±10-20 km
# error is immaterial at forecast scale.
COUNTY_CENTROIDS = {
    "Marion": (39.78, -86.14), "Allen": (41.09, -85.07),
    "Lake": (41.42, -87.37), "Hamilton": (40.07, -86.05),
    "Elkhart": (41.60, -85.87), "St. Joseph": (41.62, -86.29),
    "Tippecanoe": (40.39, -86.89), "Hendricks": (39.77, -86.51),
    "Vanderburgh": (38.02, -87.59), "Bartholomew": (39.20, -85.90),
    "Johnson": (39.49, -86.10), "Delaware": (40.23, -85.40),
    "Porter": (41.46, -87.07), "Madison": (40.16, -85.72),
    "Kosciusko": (41.24, -85.86), "Monroe": (39.16, -86.52),
    "Hancock": (39.82, -85.77), "Noble": (41.40, -85.42),
    "Vigo": (39.43, -87.39), "Cass": (40.76, -86.35),
    "Boone": (40.05, -86.47), "Lagrange": (41.64, -85.43),
    "Marshall": (41.32, -86.26), "Jackson": (38.91, -86.04),
    "Laporte": (41.55, -86.74),
}

# County -> Phase 2 metro mapping (for blending with the static search-
# economics shares). Counties not listed roll into "other_in".
COUNTY_TO_METRO = {
    "Marion": "indianapolis", "Hamilton": "indianapolis",
    "Hendricks": "indianapolis", "Johnson": "indianapolis",
    "Boone": "indianapolis", "Hancock": "indianapolis",
    "Madison": "indianapolis", "Morgan": "indianapolis",
    "Shelby": "indianapolis",
    "Allen": "fortwayne", "Whitley": "fortwayne", "Wells": "fortwayne",
    "Noble": "fortwayne", "Dekalb": "fortwayne", "Huntington": "fortwayne",
    "Lake": "nwindiana", "Porter": "nwindiana", "Laporte": "nwindiana",
    "Jasper": "nwindiana", "Newton": "nwindiana",
    "St. Joseph": "southbend", "Elkhart": "southbend",
    "Marshall": "southbend", "Kosciusko": "southbend",
    "Lagrange": "southbend",
    "Tippecanoe": "lafayette", "Clinton": "lafayette",
    "White": "lafayette", "Carroll": "lafayette",
    "Vanderburgh": "evansville", "Warrick": "evansville",
    "Posey": "evansville", "Gibson": "evansville",
}

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
# INDOT / 511in.org event feeds, tried in order. The api/v2 endpoint is the
# Castle Rock standard (same as 511GA/511NY); it may require a free
# developer key appended as ?key=... — set TRAFFICWISE_API_KEY if so.
TRAFFICWISE_EVENTS_URLS = [
    "https://511in.org/api/v2/get/event?format=json",
    "https://content.trafficwise.org/json/cars.json",
]
TRAFFICWISE_API_KEY = None  # e.g. "abc123" if 511in requires registration

# If the GitHub Actions poller is set up, its raw incident-history URL,
# e.g. "https://raw.githubusercontent.com/USER/REPO/main/incident_history.json"
# Colab runs will merge this machine-built archive into local memory.
INCIDENT_LOG_URL = None

# Weather multipliers (FHWA road-weather program; Qiu & Nixon 2008;
# Theofilatos & Yannis 2014 — conservative midpoints).
WEATHER_MULTIPLIERS = {
    "rain_light": 1.25, "rain_moderate": 1.5, "rain_heavy": 1.8,
    "snow_light": 1.5, "snow_moderate": 1.8, "snow_heavy": 2.2,
    "freezing_precip": 2.5, "fog": 1.4, "darkness": 1.25, "high_wind": 1.15,
}
MAX_MULTIPLIER = 3.5
INCIDENT_BOOST_PER_EVENT = 0.10   # +10% county risk per active event
TRAILING_BOOST_PER_POINT = 0.05   # +5% per point of decayed trailing weight
INCIDENT_BOOST_CAP = 1.75         # cap on combined live + trailing boost
TRAILING_HALF_LIFE_H = 48         # trailing importance halves every 48 h

# Hour-of-week exposure fallback (INDOT diurnal shape). Upgrade path: learn
# this empirically from EMS run timestamps if a filtered extract with a
# datetime column is provided.
WEEKDAY_HOURLY = [0.25,0.15,0.12,0.12,0.25,0.6,1.3,1.9,1.6,1.2,1.15,1.25,
                  1.35,1.35,1.5,1.8,2.0,2.1,1.6,1.1,0.85,0.7,0.55,0.4]
WEEKEND_HOURLY = [0.45,0.3,0.25,0.15,0.15,0.25,0.45,0.7,1.0,1.3,1.5,1.6,
                  1.65,1.6,1.55,1.5,1.45,1.4,1.3,1.1,0.95,0.8,0.7,0.55]

# Budget blending: forecast may move up to this fraction of allocation away
# from the static Phase 2 shares.
DYNAMIC_WEIGHT = 0.35
STATIC_SHARES = {
    "indianapolis": 0.50, "fortwayne": 0.15, "nwindiana": 0.13,
    "southbend": 0.10, "lafayette": 0.06, "evansville": 0.06,
}
