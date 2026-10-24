"""URL canonicalisation: one key per piece of content, whichever feed it came from."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DROP_PARAMS = {
    "ref", "ref_src", "ref_url", "source", "fbclid", "gclid", "mc_cid", "mc_eid", "si",
    "feature", "share", "cmpid", "s",
}
ARXIV_RE = re.compile(r"^/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5}|[a-z-]+(?:\.[A-Z]{2})?/[0-9]{7})(?:v\d+)?(?:\.pdf)?/?$")
YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def canonical_key(url: str) -> str:
    """A stable dedupe key for `url`. Not a fetchable URL; use `clean_url` for links."""
    url = (url or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m.") and host[2:] in {"youtube.com", "wikipedia.org"}:
        host = host[2:]
    path = parts.path or "/"
    if host in {"arxiv.org", "export.arxiv.org"}:
        m = ARXIV_RE.match(path)
        if m:
            return f"arxiv:{m.group(1)}"
    if host == "youtu.be" and YT_ID_RE.match(path.strip("/")):
        return f"youtube:{path.strip('/')}"
    if host == "youtube.com":
        q = dict(parse_qsl(parts.query))
        if path == "/watch" and YT_ID_RE.match(q.get("v", "")):
            return f"youtube:{q['v']}"
        m = re.match(r"^/shorts/([A-Za-z0-9_-]{11})", path)
        if m:
            return f"youtube:{m.group(1)}"
    if host == "news.ycombinator.com" and path == "/item":
        q = dict(parse_qsl(parts.query))
        if q.get("id", "").isdigit():
            return f"hn:{q['id']}"
    if host in {"reddit.com", "old.reddit.com", "new.reddit.com"}:
        m = re.match(r"^/r/[^/]+/comments/([a-z0-9]+)", path)
        if m:
            return f"reddit:{m.group(1)}"
    query = urlencode(sorted(
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in DROP_PARAMS
    ))
    if len(path) > 1:
        path = path.rstrip("/")
    port = f":{parts.port}" if parts.port and parts.port not in (80, 443) else ""
    return urlunsplit(("", host + port, path, query, "")).lstrip("/")


def clean_url(url: str) -> str:
    """The link to show: tracking parameters and fragments removed, otherwise unchanged."""
    url = (url or "").strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return url
    query = urlencode([
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"ref", "ref_src", "fbclid", "gclid", "si"}
    ])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))
