#!/usr/bin/env python3
"""Regenerate the synthetic capture files: python3 fixtures/backlog/make_capture.py

Two fictional accounts' files in the shape tools/x-bookmarks-capture.js saves: each page is a
Bookmarks response as X's web API returns it (timeline entries "tweet-<id>" and cursors). The
handles, posts and links are made up. Page n hands out the cursor "c<n>" for the next page, so a
later page with that cursor answers it. What the fixtures exercise:

- acct_alpha: a plain post with a link, a post X wraps in TweetWithVisibilityResults, a deleted
  post (tombstone), a retweet (read as the original), a quote, the same page entry twice, and a
  last page with only cursors (the end of the list).
- acct_beta: the same post alpha bookmarked (cross-account duplicate), another post linking to
  the same article as alpha's first (merged by link), and one post of its own.
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "capture"


def user(handle):
    return {"result": {"__typename": "User", "rest_id": "7", "core": {"screen_name": handle, "name": handle}}}


def tweet(tid, handle, text, links=(), created="Mon Nov 02 15:00:00 +0000 2026", **extra):
    return {"__typename": "Tweet", "rest_id": tid, "core": {"user_results": user(handle)},
            "legacy": {"id_str": tid, "full_text": text, "created_at": created, "bookmarked": True,
                       "entities": {"urls": [{"url": "https://t.co/x", "expanded_url": u} for u in links]},
                       **extra.pop("legacy", {})},
            **extra}


def entry(tid, result):
    return {"entryId": f"tweet-{tid}", "sortIndex": tid,
            "content": {"entryType": "TimelineTimelineItem", "__typename": "TimelineTimelineItem",
                        "itemContent": {"itemType": "TimelineTweet", "__typename": "TimelineTweet",
                                        "tweet_results": {"result": result}}}}


def cursors(n):
    return [{"entryId": f"cursor-top-{n}", "content": {"cursorType": "Top", "value": f"top{n}"}},
            {"entryId": f"cursor-bottom-{n}", "content": {"cursorType": "Bottom", "value": f"c{n}"}}]


def page(cursor, entries, n):
    body = {"data": {"bookmark_timeline_v2": {"timeline": {"instructions": [
        {"type": "TimelineAddEntries", "entries": entries + cursors(n)}]}}}}
    return {"cursor": cursor, "status": 200, "body": body}


def capture(account, pages, posts_seen):
    """posts_seen is what the panel would have counted: distinct post entries, deleted ones too."""
    return {"format": "tech-digest/x-bookmarks-capture", "version": 1, "account": account,
            "saved_at": "2026-11-23T18:00:00.000Z", "posts_seen": posts_seen, "first_page": True,
            "reached_end": True, "pages": pages}


A1 = tweet("3100000000000000001", "fixture_dev", "Notes on reviewer agents https://t.co/x",
           ["https://example.org/reviewers?utm_source=twitter"], created="Tue Nov 03 02:00:00 +0000 2026")
A2 = {"__typename": "TweetWithVisibilityResults",
      "tweet": tweet("3100000000000000002", "limited_fixture", "A lint for skills https://t.co/x",
                     ["https://github.com/example/skill-lint"])}
A3 = {"__typename": "TweetTombstone", "tombstone": {"text": {"text": "This post is unavailable."}}}
ORIGINAL = tweet("3100000000000000005", "onnx_fixture", "Running ONNX in the browser https://t.co/x",
                 ["https://example.org/onnx-webgpu"])
A4 = tweet("3100000000000000004", "booster_fixture", "RT @onnx_fixture: Running ONNX…",
           legacy={"retweeted_status_result": {"result": ORIGINAL}})
QUOTED = tweet("3100000000000000009", "writer_fixture", "Our evals write-up https://t.co/x",
               ["https://example.org/evals"])
A6 = tweet("3100000000000000006", "fixture_dev", "Worth a read", quoted_status_result={"result": QUOTED})

B7 = tweet("3100000000000000007", "other_fixture", "Same article https://t.co/x",
           ["https://example.org/reviewers?utm_source=newsletter"])
B8 = tweet("3100000000000000008", "beta_fixture", "Sandboxing agents https://t.co/x",
           ["https://example.org/sandboxing"], created="Sun Oct 04 09:00:00 +0000 2026")

FILES = {
    "x-bookmarks-acct_alpha-2026-11-23.json": capture("acct_alpha", [
        page(None, [entry("3100000000000000001", A1), entry("3100000000000000002", A2),
                    entry("3100000000000000003", A3)], 1),
        page("c1", [entry("3100000000000000004", A4), entry("3100000000000000006", A6),
                    entry("3100000000000000001", A1)], 2),
        page("c2", [], 3),
    ], 5),
    "x-bookmarks-acct_beta-2026-11-23.json": capture("acct_beta", [
        page(None, [entry("3100000000000000001", A1), entry("3100000000000000007", B7),
                    entry("3100000000000000008", B8)], 1),
        page("c1", [], 2),
    ], 3),
}

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, data in FILES.items():
        (OUT / name).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        print(OUT / name)
