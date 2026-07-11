"""Perigee API — FastAPI entrypoint and route registration.

Run from the backend/ directory:  uvicorn main:app --reload
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import get_conn, init_db
from routes import edgar, jets, narrative, satellite, trends
from schemas import Store

app = FastAPI(title="Perigee API")

allowed_origins = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/stores", response_model=list[Store])
def list_stores():
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM stores ORDER BY id").fetchall()
    finally:
        conn.close()
    return [Store(**dict(r)) for r in rows]


app.include_router(satellite.router)
app.include_router(trends.router)
app.include_router(jets.router)
app.include_router(edgar.router)
app.include_router(narrative.router)
