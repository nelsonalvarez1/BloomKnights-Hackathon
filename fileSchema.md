perigee/
│
│  ══════════════════════════════════════════════════════════════════════
│  CURRENT ARCHITECTURE — the signal funnel (supersedes the jet-centric
│  diagram lower in this file):
│
│      IMPORTS (supply in)  →  SATELLITE (activity)  →  TRENDS (demand)
│                          ↓
│                   FUSED ACTIVITY SCORE  →  EDGAR (files days later = edge)
│
│  • Imports = US customs bill-of-lading container volume (backend/routes/
│    imports.py, ingestion/import_ingest.py) — the supply-side leading signal.
│  • Score = backend/fusion.py, weights {imports .35, satellite .35, trend .30}.
│  • Corporate jets are DEMOTED: still shown on the map as a secondary
│    insider-intent flag, but no longer part of the score.
│  • CCTV is gone (was replaced by Google Trends as the demand signal).
│  ══════════════════════════════════════════════════════════════════════
│
├── README.md
├── .env.example                   # Gemini key, OpenSky client_id/secret
│                                   # (no key needed for Trends or EDGAR)
├── .gitignore                     # .env, __pycache__, node_modules, *.db
│
├── backend/                       # Sameer's domain (FastAPI + SQLite)
│   ├── main.py
│   ├── database.py
│   ├── perigee.db                 # gitignored, created at runtime
│   │
│   ├── routes/
│   │   ├── satellite.py           # /api/satellite — serves Dominic's output
│   │   ├── trends.py               # /api/trends — serves Sally's Google Trends data
│   │   ├── jets.py                # /api/jets — serves Sally's OpenSky data
│   │   ├── edgar.py                # /api/edgar — filing timeline
│   │   └── narrative.py           # /api/narrative — triggers Gemini call
│   │
│   └── schemas.py                 # Shared Pydantic models — the contract
│                                   # everyone codes against, defined hour 1
│
├── ml/                             # Dominic's domain (detection, satellite only now)
│   ├── detect_satellite.py        # YOLOv8 on static NAIP images → JSON
│   ├── models/
│   │   └── yolov8n.pt
│   └── sample_images/
│       ├── site_before.jpg
│       └── site_after.jpg
│
├── signals/                        # Nelson's domain (fusion + prediction math)
│   ├── fusion.py                  # NOW: calibrates Trends interest against
│                                   # satellite ground-truth (replaces old CCTV fusion)
│   ├── jet_proximity.py           # haversine distance + time-window flagging
│   ├── activity_score.py          # combines satellite + trends + jets into one score
│   └── config.py                  # locked CIKs, site coordinates, tail numbers,
│                                   # search terms for Trends — single source of truth
│
├── ingestion/                      # Sally's domain (external API plumbing)
│   ├── opensky_client.py          # OAuth token handling + refresh logic
│   ├── fetch_jets.py
│   ├── trends_client.py           # NEW: pytrends wrapper, handles the unofficial-
│                                   # API instability (retry/backoff logic)
│   ├── fetch_trends.py            # NEW: pulls interest-over-time for locked
│                                   # company/product search terms → JSON
│   ├── edgar_client.py
│   ├── fetch_filings.py
│   └── fallback/
│       ├── cached_snapshot.json   # now includes a cached Trends pull too —
│                                   # important since pytrends can be flaky live
│       └── demo_backup.mp4
│
├── gemini/                         # Dominic + Nelson pair here (hr 7)
│   └── generate_narrative.py      # payload now: satellite counts + trends
│                                   # interest + jet events + EDGAR dates
│
└── frontend/                       # Sameer's domain (React)
    ├── package.json
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   │   ├── ImageCompare.jsx    # satellite before/after imagery
    │   │   ├── JetMap.jsx          # jet position map
    │   │   ├── TrendsChart.jsx     # NEW: replaces LiveCount.jsx — search
    │   │   ├── EdgarTimeline.jsx   # the "Day 0 vs Day X" panel — your money shot
    │   │   ├── Narrative.jsx       # Gemini output display
    │   │   └── PaywallModal.jsx    # pricing tiers
    │   └── api.js                  # fetch calls to backend, matches schemas.py




    ┌─────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCE LAYER                            │
└─────────────────────────────────────────────────────────────────────┘

[NAIP GeoTIFF]          [Google Trends]      [OpenSky ADS-B]   [SEC EDGAR]
      │                       │                     │               │
      ▼                       │                     │               │
[Crop to site bbox]           │                     │               │
      │                       │                     │               │
      ▼                       │                     │               │
[Convert GeoTIFF→RGB JPG]     │                     │               │
      │                       │                     │               │
      ▼                       ▼                     ▼               ▼
[YOLOv8 detection]     [pytrends: interest    [Tail-number      [submissions API:
 conf=0.25, class=car   over time, per         proximity check    Form 4 / 8-K
 → count + boxes]       locked company]        vs. site coords]   dates per CIK]
      │                       │                     │               │
      ▼                       │                     │               │
[Annotated overlay            │                     │               │
 image for display]           │                     │               │
      │                       │                     │               │
      └──────────┬────────────┴──────────┬──────────┘               │
                  ▼                       ▼                          │
                                                                      │
      [yfinance: bulk historical    [Finnhub: live quote —           │
       baseline, ALL ~50 tickers,    only for names the fusion       │
       one-time cached pull]         layer flags as active]          │
                  │                       │                          │
                  └───────────┬───────────┘                          │
                              ▼                                      │
┌─────────────────────────────────────────────────────────────────────┐
│                          FUSION LAYER (Nelson)                       │
│  • Regression: Trends interest calibrated against satellite counts   │
│  • Jet-proximity flag (haversine, time-windowed)                     │
│  • Combined "activity score" per company                             │
│  • EDGAR filing-lag calc: signal date vs. official filing date       │
│  • Flags which of the ~50 companies are "active" → triggers          │
│    Finnhub live lookup for just those names                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     GEMINI REASONING LAYER                           │
│  Input: satellite images + counts, Trends series, jet events,        │
│         price context, EDGAR filing dates                            │
│  Output: written thesis + confidence level, citing specific evidence │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   BACKEND (Sameer) — FastAPI + SQLite                │
│  Routes: /satellite /trends /jets /edgar /prices /narrative          │
│  Cached fallback layer for every source (Trends/OpenSky most fragile)│
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  FRONTEND (Sameer) — React dashboard                 │
│  Image compare (satellite + boxes) │ Trends chart │ Jet map          │
│  EDGAR timeline (Day 0 vs Day X — the money shot)                    │
│  Price overlay on timeline │ Gemini narrative │ Paywall modal        │
└─────────────────────────────────────────────────────────────────────┘
