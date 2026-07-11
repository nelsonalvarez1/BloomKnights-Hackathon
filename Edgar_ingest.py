"""
Hour 3 - EDGAR ingestion script for Nelson's locked CIKs.

Pulls the submissions endpoint for each locked CIK, filters to Form 4 /
8-K, and writes a clean JSON that Nelson consumes directly for the
filing-lag calculation.

Run:
  python edgar_ingest.py
"""

import json
import time
from datetime import datetime, timezone

import requests

# --- EDIT: your real contact email (SEC will block bad/missing UAs)
USER_AGENT = "Perigee-Hackathon-Demo contact@example.com"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

# --- EDIT: Nelson's final locked CIKs (Hr1 task on his end), 10-digit
# zero-padded strings. Placeholder is Apple only.
LOCKED_CIKS = {
    "Apple": "0000320193",
}

TARGET_FORMS = {"4", "8-K"}


def get_submissions(cik: str) -> dict:
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def extract_filings(data: dict) -> list:
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accns = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    out = []
    for form, date, accn, doc in zip(forms, dates, accns, primary_docs):
        if form not in TARGET_FORMS:
            continue
        accn_nodash = accn.replace("-", "")
        out.append({
            "form": form,
            "filingDate": date,
            "accessionNumber": accn,

            "url": (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{int(data.get('cik'))}/{accn_nodash}/{doc}"
            ),
        })
    return out


def build_payload(name: str, cik: str, filings: list) -> dict:
    return {
        "source": "edgar",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "company": name,
        "cik": cik,
        "filings": filings,
    }


def run(out_path: str = "edgar_latest.json") -> dict:
    all_results = {}
    for name, cik in LOCKED_CIKS.items():
        data = get_submissions(cik)
        filings = extract_filings(data)
        all_results[name] = build_payload(name, cik, filings)
        print(f"OK - {name} (CIK {cik}): {len(filings)} Form 4/8-K filings")
        time.sleep(0.2)
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Written to {out_path}")
    return all_results


if __name__ == "__main__":
    run()
