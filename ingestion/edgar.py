"""
Hour 1 - EDGAR raw API smoke test.

SEC EDGAR requires NO API key, but it DOES require a descriptive
User-Agent header identifying you/your app + a contact email, or
you'll get blocked with a 403. Set this correctly once, here, and
every downstream script (Hr 3 ingestion) should reuse this same
header pattern.

Docs: https://www.sec.gov/os/webmaster-faq#developers

Run:
  python edgar_test.py
"""

import requests

# --- EDIT THIS: SEC asks for a real contact so they can reach you if your
# script misbehaves. Any real email works.
USER_AGENT = "Perigee-Hackathon-Demo contact@example.com"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov",
}

# Apple Inc. CIK, zero-padded to 10 digits -> good default smoke-test target
# since it's guaranteed to have recent Form 4 / 8-K filings.
TEST_CIK = "0000320193"


def get_submissions(cik: str) -> dict:
    """
    Pulls the full filing history/metadata for a CIK.
    This is the same endpoint the real Hr 3 ingestion script will use,
    just filtered down for the smoke test.
    """
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def recent_form4_and_8k(data: dict, limit: int = 5):
    """
    Filters the 'recent' filings block down to Form 4 / 8-K only,
    which is exactly what Nelson needs for the filing-lag calc.
    """
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accns = recent.get("accessionNumber", [])

    hits = []
    for form, date, accn in zip(forms, dates, accns):
        if form in ("4", "8-K"):
            hits.append({"form": form, "filingDate": date, "accessionNumber": accn})
        if len(hits) >= limit:
            break
    return hits


if __name__ == "__main__":
    data = get_submissions(TEST_CIK)
    name = data.get("name")
    print(f"OK - pulled submissions for {name} (CIK {TEST_CIK})")

    hits = recent_form4_and_8k(data)
    print(f"Found {len(hits)} recent Form 4 / 8-K filings:")
    for h in hits:
        print(f"  {h['filingDate']}  {h['form']:>4}  accn={h['accessionNumber']}")
