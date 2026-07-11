"""Live SEC EDGAR client — pulls real filings from data.sec.gov at request time.

No API key required; SEC only asks for a descriptive User-Agent with a contact
email (set SEC_USER_AGENT, or it uses a sane default). This is the one external
source that is both central to the pitch and reliable enough to call live on
stage — mega-caps file Form 4 / 8-K constantly, so there's always fresh data.

routes/edgar.py calls fetch_live_filings() first and falls back to the seeded
DB rows if the network hiccups, so the demo is live when it can be and never
hard-fails when it can't.
"""

import os
from datetime import date

import httpx

SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT", "Perigee-Hackathon-Demo contact@example.com"
)
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
WANTED_FORMS = {"4", "8-K", "10-Q", "10-K"}

# Map SEC's raw form codes to the labels the rest of the app / UI expect.
FORM_LABEL = {"4": "Form 4", "8-K": "8-K", "10-Q": "10-Q", "10-K": "10-K"}

FORM_DESCRIPTION = {
    "4": "Insider transaction reported by a Section 16 officer.",
    "8-K": "Material event disclosure.",
    "10-Q": "Quarterly report.",
    "10-K": "Annual report.",
}


def _headers() -> dict:
    return {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }


def _archive_url(cik: str, accession: str, primary_doc: str) -> str:
    """Deep link to the actual filing document (not just the browse page)."""
    cik_int = int(cik)
    accn_nodash = accession.replace("-", "")
    if primary_doc:
        return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accn_nodash}/{primary_doc}"
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accn_nodash}/{accession}-index.htm"


def fetch_live_filings(cik: str, since: str | None = None, limit: int = 6) -> list[dict]:
    """Return real filings for a CIK as a list of dicts matching schemas.Filing
    (form_type, filed_at, url, description), oldest-first.

    If `since` (ISO date) is given, only filings on/after that date are returned
    — that's how routes/edgar.py measures lead time against our signal. Raises
    on any network/parse error so the caller can fall back to cached rows.
    """
    resp = httpx.get(SUBMISSIONS_URL.format(cik=cik), headers=_headers(), timeout=12)
    resp.raise_for_status()
    recent = resp.json()["filings"]["recent"]

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accns = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])
    descs = recent.get("primaryDocDescription", [])

    rows = []
    for i, form in enumerate(forms):
        if form not in WANTED_FORMS:
            continue
        filed_at = dates[i]
        if since and filed_at < since:
            continue
        rows.append({
            "form_type": FORM_LABEL.get(form, form),
            "filed_at": filed_at,
            "url": _archive_url(cik, accns[i], docs[i] if i < len(docs) else ""),
            "description": (descs[i] if i < len(descs) and descs[i]
                            else FORM_DESCRIPTION.get(form, "SEC filing.")),
        })

    # SEC returns newest-first; sort oldest-first so [0] is the first filing
    # after the signal (the lead-time anchor).
    rows.sort(key=lambda r: r["filed_at"])
    return rows[:limit]
