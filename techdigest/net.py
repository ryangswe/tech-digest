"""HTTP GET with a polite User-Agent, gzip, a timeout and one retry. Plus the fixture getter."""

from __future__ import annotations

import gzip
import ssl
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path


class FetchError(RuntimeError):
    pass


def http_get(url: str, user_agent: str, timeout: float = 20, retries: int = 1,
             sleep=time.sleep) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/atom+xml, application/rss+xml, application/xml, application/json, text/html;q=0.9, */*;q=0.5",
    })
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower()
            if enc == "gzip" or body[:2] == b"\x1f\x8b":
                body = gzip.decompress(body)
            elif enc == "deflate":
                body = zlib.decompress(body)
            return body
        except urllib.error.HTTPError as e:
            reason = e.headers.get("x-deny-reason") if e.headers else None
            last = FetchError(f"HTTP {e.code}" + (f" ({reason})" if reason else ""))
            if e.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", e)
            last = FetchError(f"network error: {reason}")
            if isinstance(reason, ssl.SSLCertVerificationError):
                last = FetchError("TLS certificate check failed (on macOS python.org builds, run "
                                  "'Install Certificates.command' or set SSL_CERT_FILE)")
                break
        if attempt < retries:
            sleep(3)
    raise last or FetchError("unknown error")


def fixture_getter(fixtures_dir: Path):
    """A getter that reads fixtures/<source-id>.<ext> instead of the network."""
    fixtures_dir = Path(fixtures_dir)

    def get(url: str, source_id: str) -> bytes:
        matches = sorted(fixtures_dir.glob(f"{source_id}.*"))
        if not matches:
            raise FetchError("no fixture")
        if matches[0].suffix == ".error":  # simulates a failing source, e.g. "HTTP 429"
            raise FetchError(matches[0].read_text().strip())
        return matches[0].read_bytes()

    return get
