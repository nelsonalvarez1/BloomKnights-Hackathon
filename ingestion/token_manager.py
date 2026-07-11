"""
Hour 4 - OpenSky token-refresh logic.

The demo cannot stall because a token expired mid-run. This wraps
get_token() in a manager that tracks expiry and transparently
refreshes when needed, so every caller just does:

    mgr = TokenManager(client_id, client_secret)
    token = mgr.get_valid_token()   # always fresh, refreshes itself

Run standalone to sanity-check refresh timing:
  python token_manager.py
"""

import time
import threading

from opensky_auth import get_token


class TokenManager:
    """Thread-safe OpenSky token holder with auto-refresh."""

    # Refresh a bit early - don't wait until the literal expiry instant
    SAFETY_MARGIN_SECONDS = 60

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def _refresh(self):
        data = get_token(self.client_id, self.client_secret)
        self._token = data["access_token"]
        expires_in = data.get("expires_in", 1800)  # default 30 min per OpenSky docs
        self._expires_at = time.time() + expires_in - self.SAFETY_MARGIN_SECONDS
        print(f"[TokenManager] refreshed, valid ~{expires_in - self.SAFETY_MARGIN_SECONDS}s")

    def get_valid_token(self) -> str:
        with self._lock:
            if self._token is None or time.time() >= self._expires_at:
                self._refresh()
            return self._token


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()  # reads the same .env file opensky_auth.py uses

    client_id = os.environ.get("OPENSKY_CLIENT_ID")
    client_secret = os.environ.get("OPENSKY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit(
            "OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET not found. Check that "
            "a .env file exists in this same folder (see opensky_auth.py)."
        )

    mgr = TokenManager(client_id, client_secret)
    t1 = mgr.get_valid_token()
    print("token acquired:", t1[:12] + "...")
    # calling again immediately should NOT trigger a refresh
    t2 = mgr.get_valid_token()
    assert t1 == t2, "should reuse the cached token when still valid"
    print("reuse check passed")
