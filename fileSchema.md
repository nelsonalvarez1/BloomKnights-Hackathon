perigee/
│
├── README.md                      # Sally owns final polish, hour 11
├── .env.example                   # API keys template (Gemini, OpenSky client_id/secret)
├── .gitignore                     # .env, __pycache__, node_modules, *.db
│
├── backend/                       # Sameer's domain (FastAPI + SQLite)
│   ├── main.py                    # FastAPI app entrypoint, route registration
│   ├── database.py                # SQLite connection + schema init
│   ├── perigee.db                 # SQLite file (gitignored, created at runtime)
│   │
│   ├── routes/
│   │   ├── satellite.py           # /api/satellite endpoints — serves Dominic's output
│   │   ├── cctv.py                # /api/cctv endpoints — live count polling
│   │   ├── jets.py                # /api/jets endpoints — serves Sally's OpenSky data
│   │   ├── edgar.py                # /api/edgar endpoints — filing timeline
│   │   └── narrative.py           # /api/narrative — triggers Gemini call
│   │
│   └── schemas.py                 # Shared Pydantic models — THE shared contract
│                                   # everyone codes against, defined hour 1
│
├── ml/                             # Dominic's domain (detection pipelines)
│   ├── detect_satellite.py        # YOLOv8 on static NAIP images → JSON
│   ├── detect_cctv.py             # YOLOv8 on live FL511 frame → JSON
│   ├── models/
│   │   └── yolov8n.pt             # pretrained weights (gitignored if large, download script instead)
│   └── sample_images/
│       ├── site_before.jpg        # pre-downloaded NAIP images
│       └── site_after.jpg
│
├── signals/                        # Nelson's domain (fusion + prediction math)
│   ├── fusion.py                  # regression: calibrate CCTV against satellite
│   ├── jet_proximity.py           # haversine distance + time-window flagging
│   ├── activity_score.py          # combines all signals into one score
│   └── config.py                  # locked CIKs, site coordinates, tail numbers —
│                                   # single source of truth, set hour 1, don't touch after
│
├── ingestion/                      # Sally's domain (external API plumbing)
│   ├── opensky_client.py          # OAuth token handling + refresh logic
│   ├── fetch_jets.py               # pull tail-number positions on a loop
│   ├── edgar_client.py             # User-Agent header, CIK submissions pull
│   ├── fetch_filings.py           # Form 4 / 8-K extraction, filing-lag calc
│   └── fallback/
│       ├── cached_snapshot.json   # safety-net data if live APIs fail
│       └── demo_backup.mp4        # recorded full-flow video, safety net
│
├── gemini/                         # Dominic + Nelson pair here (hr 7)
│   └── generate_narrative.py      # prompt template + API call, takes
│                                   # combined signal payload → written thesis
│
└── frontend/                       # Sameer's domain (React)
    ├── package.json
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   │   ├── ImageCompare.jsx    # satellite before/after + bounding boxes
    │   │   ├── LiveCount.jsx       # CCTV live count panel
    │   │   ├── JetMap.jsx          # jet position map
    │   │   ├── EdgarTimeline.jsx   # the "Day 0 vs Day X" panel — your money shot
    │   │   ├── Narrative.jsx       # Gemini output display
    │   │   └── PaywallModal.jsx    # pricing tiers
    │   └── api.js                  # fetch calls to backend, matches schemas.py
