"""Parsers: raw bytes from one source -> list of Items. Pure functions, no network."""

from __future__ import annotations

import hashlib
import html
import html.entities
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from .config import Source
from .items import Item
from .text import html_blocks, html_to_text, parse_date
from .urls import clean_url

XML_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}


class ParseError(ValueError):
    pass


def _decode(raw: bytes | str) -> str:
    if isinstance(raw, str):
        return raw
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _fix_entities(text: str) -> str:
    """Feeds often use HTML entities (&nbsp;) that XML does not define."""
    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name in XML_ENTITIES:
            return m.group(0)
        cp = html.entities.name2codepoint.get(name)
        return f"&#{cp};" if cp else f"&amp;{name};"
    return re.sub(r"&([A-Za-z][A-Za-z0-9]*);", repl, text)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _xml_root(raw: bytes | str) -> ET.Element:
    text = _decode(raw).lstrip()
    text = re.sub(r"^<\?xml[^>]*\?>", "", text).lstrip()
    try:
        root = ET.fromstring(_fix_entities(text))
    except ET.ParseError as e:
        raise ParseError(f"not valid XML: {e}")
    for el in root.iter():
        el.tag = _local(el.tag)
        el.attrib = {_local(k): v for k, v in el.attrib.items()}
    return root


def _child_text(el: ET.Element, *names: str) -> str:
    for name in names:
        c = el.find(name)
        if c is not None:
            text = "".join(c.itertext()).strip()
            if text:
                return text
    return ""


def _atom_link(entry: ET.Element) -> str:
    links = entry.findall("link")
    for ln in links:
        if ln.get("rel", "alternate") == "alternate" and ln.get("href"):
            return ln.get("href")
    return links[0].get("href", "") if links else ""


def parse_feed(raw: bytes | str, src: Source) -> list[Item]:
    """RSS 2.0, RSS 1.0 (RDF) and Atom, including GitHub, YouTube, Reddit and arXiv flavours."""
    root = _xml_root(raw)
    items: list[Item] = []
    if root.tag == "feed":  # Atom
        for e in root.findall("entry"):
            title = html_to_text(_child_text(e, "title"))
            url = _atom_link(e)
            content_html = _child_text(e, "content", "summary")
            if not content_html:  # YouTube puts the description under media:group
                group = e.find("group")
                if group is not None:
                    content_html = _child_text(group, "description")
            date = parse_date(_child_text(e, "published", "updated"))
            item = Item(src.id, title, clean_url(url), html_to_text(content_html), date)
            if src.flavor == "reddit":
                item = _reddit(item, content_html, e)
            items.append(item)
    else:  # RSS 2.0 (<rss><channel><item>) or RDF (<rdf:RDF><item>)
        for e in root.iter("item"):
            title = html_to_text(_child_text(e, "title"))
            url = _child_text(e, "link")
            guid = e.find("guid")
            if not url and guid is not None and guid.get("isPermaLink", "true") != "false":
                url = (guid.text or "").strip()
            body = _child_text(e, "description", "encoded", "summary")
            date = parse_date(_child_text(e, "pubDate", "date", "published", "updated"))
            items.append(Item(src.id, title, clean_url(url), html_to_text(body), date))
    return [i for i in items if i.title and i.url.startswith(("http://", "https://"))]


def _reddit(item: Item, content_html: str, entry: ET.Element) -> Item:
    """Reddit link posts: point at the linked page, keep the thread as the discussion."""
    permalink = item.url
    cat = entry.find("category")
    sub = cat.get("label") if cat is not None and cat.get("label") else "Reddit"
    external = ""
    m = re.search(r'<a href="([^"]+)">\s*\[link\]\s*</a>', content_html or "")
    if m:
        href = html.unescape(m.group(1))
        host = (urlsplit(href).hostname or "").lower()
        if host and not host.endswith(("reddit.com", "redd.it")):
            external = clean_url(href)
    summary = re.sub(r"\s*submitted by\s+/u/\S+.*$", "", item.summary).strip()
    return Item(
        item.source, item.title, external or permalink, summary, item.published,
        discussions=[{"name": sub, "url": permalink}],
    )


def parse_arxiv(raw: bytes | str, src: Source) -> list[Item]:
    items = []
    for it in parse_feed(raw, src):
        m = re.search(r"arxiv\.org/abs/([^v\s]+)", it.url)
        if m:
            it.url = f"https://arxiv.org/abs/{m.group(1)}"
            it.key = f"arxiv:{m.group(1)}"
        it.title = re.sub(r"\s+", " ", it.title)
        items.append(it)
    return items


def parse_hn(raw: bytes | str, src: Source) -> list[Item]:
    try:
        data = json.loads(_decode(raw))
    except json.JSONDecodeError as e:
        raise ParseError(f"not valid JSON: {e}")
    items = []
    for h in data.get("hits", []):
        title = (h.get("title") or h.get("story_title") or "").strip()
        oid = h.get("objectID") or h.get("story_id")
        if not title or not oid:
            continue
        thread = f"https://news.ycombinator.com/item?id={oid}"
        points, comments = h.get("points"), h.get("num_comments")
        label = "HN"
        if points is not None:
            label += f" · {points} points"
        ts = h.get("created_at_i")
        date = datetime.fromtimestamp(ts, timezone.utc) if ts else parse_date(h.get("created_at"))
        summary = html_to_text(h.get("story_text") or "")
        items.append(Item(
            src.id, html.unescape(title), clean_url(h.get("url") or thread), summary, date,
            discussions=[{"name": label, "url": thread, "points": points, "comments": comments}],
            points=points,
        ))
    return items


# --- HTML listing pages --------------------------------------------------------------------

class _LinkParser(HTMLParser):
    """Collect each <a href>'s candidate titles: heading text, image alt, plain text."""

    HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[dict] = []
        self.cur: dict | None = None
        self.heading = 0
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "svg"):
            self.skip += 1
        if tag == "a":
            self.cur = {"href": a.get("href") or "", "heads": [], "alts": [], "texts": [""]}
            self.links.append(self.cur)
        elif self.cur is not None:
            if tag in self.HEADINGS:
                self.heading += 1
                self.cur["heads"].append("")
            elif tag == "img" and a.get("alt"):
                self.cur["alts"].append(a["alt"].strip())
            elif tag in ("span", "div", "p", "br", "time"):
                self.cur["texts"].append("")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg"):
            self.skip = max(0, self.skip - 1)
        if tag == "a":
            self.cur = None
            self.heading = 0
        elif self.cur is not None:
            if tag in self.HEADINGS:
                self.heading = max(0, self.heading - 1)
            if tag in ("span", "div", "p", "time") or tag in self.HEADINGS:
                self.cur["texts"].append("")

    def handle_data(self, data):
        if self.cur is None or self.skip:
            return
        if self.heading and self.cur["heads"]:
            self.cur["heads"][-1] += data
        self.cur["texts"][-1] += data


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_html_links(raw: bytes | str, src: Source) -> list[Item]:
    """New article links on a listing page. Undated, so fetch bootstraps them on first sight."""
    p = _LinkParser()
    p.feed(_decode(raw))
    base_host = (urlsplit(src.url).hostname or "").lower()
    pattern = re.compile(src.pattern or "")
    best: dict[str, tuple[int, str]] = {}
    order: list[str] = []
    for ln in p.links:
        url = urljoin(src.url, html.unescape(ln["href"]))
        parts = urlsplit(url)
        if (parts.hostname or "").lower() != base_host or not pattern.search(parts.path):
            continue
        if parts.path.rstrip("/") in {e.rstrip("/") for e in src.exclude_paths}:
            continue
        url = clean_url(url)
        heads = [_clean(h) for h in ln["heads"] if _clean(h)]
        alts = [_clean(a) for a in ln["alts"] if _clean(a)]
        texts = sorted((_clean(t) for t in ln["texts"] if _clean(t)), key=len, reverse=True)
        cand = [(3, h) for h in heads] + [(2, a) for a in alts] + [(1, t) for t in texts]
        cand = [c for c in cand if len(c[1]) >= src.min_title_chars]
        if url not in best:
            order.append(url)
            best[url] = (0, "")
        if cand and cand[0][0] > best[url][0]:
            best[url] = cand[0]
    return [Item(src.id, best[u][1][:200], u) for u in order if best[u][1]]


# --- Page watches --------------------------------------------------------------------------

def page_paragraphs(raw: bytes | str) -> list[str]:
    """The page's readable text as paragraphs, without navigation and chrome."""
    blocks = html_blocks(_decode(raw), skip={"nav", "header", "footer", "aside", "form", "button"})
    return [b for b in blocks if len(b) >= 3]


def paragraph_hashes(paragraphs: list[str]) -> list[str]:
    return [hashlib.sha1(p.encode()).hexdigest()[:10] for p in paragraphs]


def page_hash(paragraphs: list[str]) -> str:
    return hashlib.sha256("\n".join(paragraphs).encode()).hexdigest()


PARSERS = {
    "feed": parse_feed,
    "arxiv": parse_arxiv,
    "hn": parse_hn,
    "html_links": parse_html_links,
}
