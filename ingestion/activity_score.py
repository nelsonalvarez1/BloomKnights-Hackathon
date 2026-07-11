"""
Hour 6  - Signal fusion: combine imports,
satellite, and Google Trends into one "confidence score," and write
out the exact real numbers that feed the Gemini prompt.

Run:
  python activity_score.py
"""

import json
import math
from datetime import datetime, timezone

# --- EDIT: your actual site coordinates (for the secondary jet flag)
SITE_LAT = 28.15
SITE_LON = -81.20

# --- EDIT: jet counts as "proximate" within this many miles
JET_PROXIMITY_MILES = 15.0

# --- EDIT: which hero company's imports score to use for the funnel
HERO_COMPANY = "WALMART INC"

# Pivot weights -> jets removed entirely, imports added as the anchor.
# Documented judgment calls, not fitted coefficients, say this plainly
# if asked.
WEIGHTS = {
    "imports": 0.35,
    "satellite": 0.35,
    "trends": 0.30,
}


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"WARN: {path} not found that signal will be scored as 0/missing")
        return None


def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def score_imports(data, hero_company: str = HERO_COMPANY) -> dict:
    if data is None or hero_company not in data.get("companies", {}):
        return {"raw_change_pct": None, "score": 0.0}
    company_data = data["companies"][hero_company]
    if "error" in company_data:
        return {"raw_change_pct": None, "score": 0.0, "note": company_data["error"]}
    return company_data


def score_satellite(data) -> dict:
    """
    Normalizes vehicle/car count to a 0-1 score. Uses car_count per the
    pivot's new schema field, falls back to vehicle_count if Dominic
    hasn't renamed it yet.
    """
    if data is None:
        return {"raw_count": None, "score": 0.0}
    count = data.get("car_count", data.get("vehicle_count", 0)) or 0
    MAX_EXPECTED = 50  # --- EDIT: calibrate against real site baseline
    score = min(count / MAX_EXPECTED, 1.0)
    return {"raw_count": count, "score": round(score, 3)}


def score_trends(data) -> dict:
    """Uses the most recent data point per term, averaged across terms."""
    if data is None or not data.get("terms"):
        return {"raw_values": {}, "score": 0.0}
    terms = data["terms"]
    latest_values = []
    per_term = {}
    for term, points in terms.items():
        if not points:
            continue
        latest = points[-1]["value"]  # 0-100 scale, Google's native range
        per_term[term] = latest
        latest_values.append(latest)
    avg = sum(latest_values) / len(latest_values) if latest_values else 0
    return {"raw_values": per_term, "score": round(avg / 100, 3)}


def secondary_jet_flag(data) -> dict:
    """
    NOT part of the fused score anymore. Reported separately as an
    "insider intent" signal - a CEO's plane near the site suggests
    something is happening, but it's a different axis than the clean
    supply->activity->demand funnel, so it doesn't get averaged in.
    """
    if data is None or not data.get("aircraft"):
        return {"nearest_distance_miles": None, "flag": False}
    distances = []
    for a in data["aircraft"]:
        if a.get("lat") is None or a.get("lon") is None:
            continue
        d = haversine_miles(SITE_LAT, SITE_LON, a["lat"], a["lon"])
        distances.append((d, a["icao24"]))
    if not distances:
        return {"nearest_distance_miles": None, "flag": False}
    nearest_dist, nearest_icao = min(distances, key=lambda x: x[0])
    return {
        "nearest_distance_miles": round(nearest_dist, 2),
        "nearest_icao24": nearest_icao,
        "flag": nearest_dist <= JET_PROXIMITY_MILES,
    }


def score_filing_lag(data, signal_detected_date: str) -> dict:
    """
    Not part of the fused score either -> this is the PROOF layer, shown
    after the score, not folded into it. days_early is your literal
    "Day 0 vs Day X" number for the EDGAR timeline reveal.
    """
    if data is None:
        return {"days_early": None}

    detected = datetime.strptime(signal_detected_date, "%Y-%m-%d")
    earliest_lag = None
    earliest_filing = None
    for company, company_data in data.items():
        for filing in company_data.get("filings", []):
            filed = datetime.strptime(filing["filingDate"], "%Y-%m-%d")
            lag = (filed - detected).days
            if lag >= 0 and (earliest_lag is None or lag < earliest_lag):
                earliest_lag = lag
                earliest_filing = {"company": company, **filing}

    if earliest_lag is None:
        return {"days_early": None}
    return {"days_early": earliest_lag, "matched_filing": earliest_filing}


def combine(components: dict) -> float:
    """Only imports/satellite/trends feed the score -> jets and filing lag do not."""
    total = sum(components[k]["score"] * WEIGHTS[k] for k in WEIGHTS)
    return round(total, 3)


def confidence_label(score: float) -> str:
    if score >= 0.7:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


def build_gemini_payload(
    components: dict, jet_flag: dict, filing_lag: dict,
    activity_score: float, signal_detected_date: str
) -> dict:
    """
    This exact dict is what gets handed to Gemini. Keep it flat and
    numeric where possible -> precise inputs produce a specific,
    defensible narrative instead of a generic one. Tell the funnel:
    imports up -> activity up -> demand up -> confidence -> filing proof.
    """
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signal_detected_date": signal_detected_date,
        "confidence_score": activity_score,
        "confidence_label": confidence_label(activity_score),
        "imports": components["imports"],
        "satellite": components["satellite"],
        "google_trends": components["trends"],
        "insider_intent_jet_flag": jet_flag,  # secondary, not scored
        "filing_lag": filing_lag,  # proof layer, not scored
        "weights_used": WEIGHTS,
    }


def run(signal_detected_date: str, out_path: str = "gemini_input.json") -> dict:
    imports_data = load_json("imports_latest.json")
    satellite_data = load_json("satellite_latest.json")
    trends_data = load_json("trends_latest.json")
    opensky_data = load_json("opensky_latest.json")
    edgar_data = load_json("edgar_latest.json")

    components = {
        "imports": score_imports(imports_data),
        "satellite": score_satellite(satellite_data),
        "trends": score_trends(trends_data),
    }
    jet_flag = secondary_jet_flag(opensky_data)
    filing_lag = score_filing_lag(edgar_data, signal_detected_date)

    activity_score = combine(components)
    payload = build_gemini_payload(components, jet_flag, filing_lag, activity_score, signal_detected_date)

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Confidence score: {activity_score} ({confidence_label(activity_score)})")
    print(json.dumps(payload, indent=2))
    print(f"Written to {out_path}")
    return payload


if __name__ == "__main__":
    # --- EDIT: the date your combined signal "fired" for the demo story
    # this is Day 0 in the "Day 0 vs Day X" EDGAR timeline narrative.
    SIGNAL_DETECTED_DATE = "2026-05-20"
    run(SIGNAL_DETECTED_DATE)
