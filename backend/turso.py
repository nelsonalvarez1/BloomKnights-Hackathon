"""Minimal Turso (libSQL) client over the Hrana HTTP "pipeline" API.

Pure Python (httpx only), so it works on Vercel's serverless runtime and on
Windows without the native libsql extension. It implements just enough of the
sqlite3 connection/cursor surface that database.py and the routes use it
unchanged: execute / executemany / executescript / fetchone / fetchall,
row["col"], dict(row), row[0], commit(), close().

Activated when TURSO_DATABASE_URL and TURSO_AUTH_TOKEN are set (see
database.get_conn). Each execute is its own autocommitting HTTP round-trip.
"""

import base64

import httpx


class Row:
    """sqlite3.Row-ish: supports row["col"], row[0], and dict(row)."""

    __slots__ = ("_cols", "_vals")

    def __init__(self, cols, vals):
        self._cols = cols
        self._vals = vals

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._vals[key]
        return self._vals[self._cols.index(key)]

    def keys(self):
        return list(self._cols)

    def __iter__(self):
        return iter(self._vals)

    def __len__(self):
        return len(self._vals)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _encode_arg(v):
    if v is None:
        return {"type": "null", "value": None}
    if isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    if isinstance(v, (bytes, bytearray)):
        return {"type": "blob", "base64": base64.b64encode(v).decode()}
    return {"type": "text", "value": str(v)}


def _decode_cell(cell):
    t = cell.get("type")
    if t == "null":
        return None
    if t == "integer":
        return int(cell["value"])
    if t == "float":
        return float(cell["value"])
    if t == "blob":
        return base64.b64decode(cell.get("base64", ""))
    return cell.get("value")


def _to_https(url):
    return url.replace("libsql://", "https://").rstrip("/")


class TursoConnection:
    def __init__(self, url, token, timeout=30):
        self._endpoint = _to_https(url) + "/v2/pipeline"
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = timeout

    def _pipeline(self, statements):
        requests = [
            {"type": "execute",
             "stmt": {"sql": sql, "args": [_encode_arg(a) for a in args]}}
            for sql, args in statements
        ]
        requests.append({"type": "close"})
        resp = httpx.post(
            self._endpoint, headers=self._headers,
            json={"requests": requests}, timeout=self._timeout,
        )
        resp.raise_for_status()
        out = []
        for item in resp.json().get("results", []):
            if item.get("type") == "error":
                raise RuntimeError(f"Turso error: {item.get('error')}")
            response = item.get("response") or {}
            if response.get("type") != "execute":
                out.append(_Result([]))
                continue
            result = response["result"]
            cols = [c["name"] for c in result.get("cols", [])]
            rows = [
                Row(cols, [_decode_cell(c) for c in row])
                for row in result.get("rows", [])
            ]
            out.append(_Result(rows))
        return out

    def execute(self, sql, params=()):
        return self._pipeline([(sql, tuple(params))])[0]

    def executemany(self, sql, seq_of_params):
        self._pipeline([(sql, tuple(p)) for p in seq_of_params])

    def executescript(self, script):
        stmts = [(s.strip(), ()) for s in script.split(";") if s.strip()]
        self._pipeline(stmts)

    def commit(self):
        pass  # each _pipeline call autocommits

    def close(self):
        pass
