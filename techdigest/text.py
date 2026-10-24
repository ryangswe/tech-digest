"""Small text helpers: HTML to plain text, truncation, keyword matching, dates."""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

BLOCK_TAGS = {
    "p", "div", "li", "ul", "ol", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "td", "th",
    "section", "article", "blockquote", "pre", "table", "dd", "dt",
}
SKIP_TAGS = {"script", "style", "noscript", "svg", "template", "head"}


class _TextParser(HTMLParser):
    def __init__(self, skip: set[str]):
        super().__init__(convert_charrefs=True)
        self.skip = skip
        self.depth = 0
        self.blocks: list[str] = []
        self.cur: list[str] = []

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self.cur)).strip()
        if text:
            self.blocks.append(text)
        self.cur = []

    def handle_starttag(self, tag, attrs):
        if tag in self.skip:
            self.depth += 1
        elif tag in BLOCK_TAGS:
            self._flush()

    def handle_startendtag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        if tag in self.skip:
            self.depth = max(0, self.depth - 1)
        elif tag in BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if not self.depth:
            self.cur.append(data)


def html_blocks(markup: str, skip: set[str] | None = None) -> list[str]:
    """Plain-text paragraphs of an HTML fragment or page."""
    p = _TextParser(SKIP_TAGS | (skip or set()))
    try:
        p.feed(markup or "")
        p.close()
    except Exception:  # malformed markup: keep what parsed
        pass
    p._flush()
    return p.blocks


def html_to_text(markup: str) -> str:
    if not markup:
        return ""
    if "<" not in markup:
        return re.sub(r"\s+", " ", html.unescape(markup)).strip()
    return " ".join(html_blocks(markup))


def truncate(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:—-")
    return cut + "…"


def truncate_words(text: str, n: int) -> str:
    words = (text or "").split()
    return text.strip() if len(words) <= n else " ".join(words[:n]).rstrip(",;:—-") + "…"


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def keyword_re(term: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])")


def matches_any(text: str, terms: list[str]) -> list[str]:
    low = (text or "").lower()
    return [t for t in terms if keyword_re(t).search(low)]


def parse_date(value: str | None) -> datetime | None:
    """RFC 822 (RSS) or ISO 8601 (Atom) to an aware UTC datetime; None if unparseable."""
    if not value:
        return None
    value = value.strip()
    dt = None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        pass
    if dt is None:
        v = value.replace("Z", "+00:00")
        if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            v += "T00:00:00+00:00"
        v = re.sub(r"\.(\d+)", lambda m: "." + (m.group(1) + "000000")[:6], v)  # any precision
        try:
            dt = datetime.fromisoformat(v)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


# --- Time zones ---------------------------------------------------------------------------

def _us_dst(dt_utc: datetime, std_offset_h: int) -> bool:
    """US rule: DST from the 2nd Sunday of March 02:00 to the 1st Sunday of November 02:00."""
    y = dt_utc.year

    def nth_sunday(month: int, n: int) -> datetime:
        d = datetime(y, month, 1)
        d += timedelta(days=(6 - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)

    # Local 02:00 standard time -> UTC, and local 02:00 daylight time -> UTC.
    start = nth_sunday(3, 2).replace(hour=2) + timedelta(hours=std_offset_h)
    end = nth_sunday(11, 1).replace(hour=2) + timedelta(hours=std_offset_h - 1)
    naive = dt_utc.astimezone(timezone.utc).replace(tzinfo=None)
    return start <= naive < end


US_ZONES = {"America/New_York": -5, "America/Chicago": -6, "America/Denver": -7, "America/Los_Angeles": -8}


def local_now(tz_name: str, now: datetime | None = None) -> datetime:
    """`now` in the configured zone. Falls back to a built-in US rule, then UTC, without tzdata."""
    now = now or datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo(tz_name))
    except Exception:
        if tz_name in US_ZONES:
            std = US_ZONES[tz_name]
            off = std + (1 if _us_dst(now, -std) else 0)
            return now.astimezone(timezone(timedelta(hours=off)))
        return now.astimezone(timezone.utc)
