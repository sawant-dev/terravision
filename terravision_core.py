"""
TerraVision — Step 3: Full Solar Site Report
Combines sunlight (NASA POWER) and land slope (NASA SRTM via OpenTopoData)
into one report with an overall site score out of 100.

Run:  python terravision_site_report.py
"""

import math
import requests

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
PERFORMANCE_RATIO = 0.78     # real plants lose ~22% to heat, dust, wiring
STEP_M = 100                 # distance of slope sample points, in metres


# ===================== DATA FUNCTIONS =====================

def get_sunlight(lat, lon):
    """Ask NASA POWER for monthly average sunlight and temperature."""
    url = "https://power.larc.nasa.gov/api/temporal/climatology/point"
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN,T2M",
        "community": "RE",
        "latitude": lat,
        "longitude": lon,
        "format": "JSON",
    }
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()["properties"]["parameter"]
    return data["ALLSKY_SFC_SW_DWN"], data["T2M"]


def get_elevations(lat, lon):
    """Get ground height at the centre and 100 m N, S, E, W."""
    dlat = STEP_M / 111_320
    dlon = STEP_M / (111_320 * math.cos(math.radians(lat)))
    points = {
        "centre": (lat, lon),
        "north":  (lat + dlat, lon),
        "south":  (lat - dlat, lon),
        "east":   (lat, lon + dlon),
        "west":   (lat, lon - dlon),
    }
    locations = "|".join(f"{a},{b}" for a, b in points.values())
    url = "https://api.opentopodata.org/v1/srtm30m"
    response = requests.get(url, params={"locations": locations}, timeout=60)
    response.raise_for_status()
    results = response.json()["results"]

    elev = {}
    for name, result in zip(points, results):
        elev[name] = result["elevation"]
    return elev


# ===================== CALCULATION FUNCTIONS =====================

def calc_slope(elev):
    """Return slope in degrees, compass angle, and direction name."""
    rise_east = (elev["east"] - elev["west"]) / (2 * STEP_M)
    rise_north = (elev["north"] - elev["south"]) / (2 * STEP_M)
    slope = math.degrees(math.atan(math.hypot(rise_east, rise_north)))
    aspect = math.degrees(math.atan2(-rise_east, -rise_north)) % 360
    names = ["North", "North-East", "East", "South-East",
             "South", "South-West", "West", "North-West"]
    facing = names[round(aspect / 45) % 8]
    return slope, aspect, facing


def clamp(value, low=0, high=100):
    """Keep a number between low and high."""
    return max(low, min(high, value))


def sunlight_score(annual_sun):
    """3.5 kWh/m²/day or less = 0 points, 6.0 or more = 100 points."""
    return clamp((annual_sun - 3.5) / (6.0 - 3.5) * 100)


def land_score(slope, facing):
    """Flat (2° or less) = 100 points, 10° or more = 0. Adjust for direction."""
    score = clamp((10 - slope) / (10 - 2) * 100)
    if slope >= 2:
        if "South" in facing:
            score += 5
        elif "North" in facing:
            score -= 15
    return clamp(score)


def verdict(score):
    if score >= 80:
        return "EXCELLENT - strongly recommended for solar"
    if score >= 65:
        return "GOOD - suitable for solar"
    if score >= 50:
        return "FAIR - possible, check costs carefully"
    return "POOR - not recommended"



# ===================== LAND USE (what's on the ground) =====================

RADIUS_M = 250      # look at everything within 250 m of the point


def get_land_use(lat, lon):
    """Count buildings, towns, water, forest and farmland near the point,
    using OpenStreetMap (free map of the world, via the Overpass API)."""
    around = f"(around:{RADIUS_M},{lat},{lon})"
    query = f"""
    [out:json][timeout:25];
    way["building"]{around};
    out count;
    nwr["landuse"~"^(residential|commercial|industrial|retail)$"]{around};
    out count;
    nwr["natural"="water"]{around};
    out count;
    (nwr["landuse"="forest"]{around}; nwr["natural"="wood"]{around};);
    out count;
    nwr["landuse"~"^(farmland|meadow|grass)$"]{around};
    out count;
    """
    url = "https://overpass-api.de/api/interpreter"
    headers = {"User-Agent": "TerraVision/0.1 (solar site assessment)"}
    response = requests.post(url, data={"data": query}, headers=headers, timeout=60)
    response.raise_for_status()
    elements = response.json()["elements"]

    names = ["buildings", "urban", "water", "forest", "farmland"]
    counts = {}
    for name, element in zip(names, elements):
        counts[name] = int(element["tags"]["total"])
    return counts


def classify_land(counts):
    """Turn the counts into a land type, a score out of 100, and buildable yes/no."""
    if counts["buildings"] >= 30 or counts["urban"] > 0:
        return "Built-up area (town/city)", 0, False
    if counts["water"] > 0:
        return "Water body nearby", 50, True
    if counts["forest"] > 0:
        return "Forest / trees nearby", 40, True
    if counts["buildings"] >= 10:
        return "Village / scattered buildings", 60, True
    if counts["farmland"] > 0:
        return "Farmland / open land", 100, True
    return "Open land (not mapped in detail)", 85, True