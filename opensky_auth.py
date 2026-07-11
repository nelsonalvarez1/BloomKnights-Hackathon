"""
Hour 1 - OpenSky OAuth2 client-credentials flow.

Register your client first at:
  https://opensky-network.org/my-opensky  (API Client -> Client ID/Secret)

Set these as envinroment variables before running:
  OPENSKY_CLIENT_ID
  OPENSKY_CLIENT_SECRET

Run:
  python opensky_auth.py
"""

import os
import time
import requests

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/"
    "protocol/openid-connect/token"
)
STATES_URL = "https://opensky-network.org/api/states/all"


def get_token(client_id: str, client_secret: str) -> dict:
    """
    Returns the full token response dict, e.g.:
      {"access_token": "...", "expires_in": 1800, "token_type": "Bearer", ...}
    Tokens expire in ~30 min (per hackathon plan, refresh logic is Hr 4).
    """
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def smoke_test(access_token: str, bbox=None):
    """
    Confirms the token actually works against a real endpoint.
    bbox = (lamin, lomin, lamax, lomax) - optional bounding box filter.
    Default here is a small box over central Florida so it's cheap to eyeball.
    """
    params = {}
    if bbox:
        lamin, lomin, lamax, lomax = bbox
        params.update({"lamin": lamin, "lomin": lomin, "lamax": lamax, "lomax": lomax})

    resp = requests.get(
        STATES_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    states = data.get("states") or []
    print(f"OK - got {len(states)} aircraft states at time={data.get('time')}")
    if states:
        # first row for a quick manual sanity check
        print("sample state:", states[0])
    return data


if __name__ == "__main__":
    client_id = os.environ.get("OPENSKY_CLIENT_ID")
    client_secret = os.environ.get("OPENSKY_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise SystemExit(
            "Set OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET env vars first."
        )

    t0 = time.time()
    token_data = get_token(client_id, client_secret)
    print(f"Token acquired in {time.time() - t0:.2f}s, "
          f"expires_in={token_data.get('expires_in')}s")

    # Central Florida bbox - adjust to your actual site location for Hr 2
    fl_bbox = (27.5, -81.8, 28.8, -80.5)
    smoke_test(token_data["access_token"], bbox=fl_bbox)
