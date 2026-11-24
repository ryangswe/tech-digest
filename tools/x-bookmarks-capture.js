// ==UserScript==
// @name         tech-digest: capture my X bookmarks
// @description  Keeps the Bookmarks responses that X's own page loads while you scroll, and saves them as one JSON file.
// @match        https://x.com/i/bookmarks*
// @run-at       document-start
// @inject-into  page
// @grant        none
// @version      1
// ==/UserScript==
//
// Read this file in full before you run it, because it is all the code there is. The steps for
// using it are in docs/x-bookmarks.md. You paste it into the browser console on x.com, or install
// it as a local userscript (the header above).
//
// X's Bookmarks page asks X's servers for your bookmarks a page at a time, as you
// scroll. This script listens for the answers to those requests (the "Bookmarks" GraphQL
// request) and keeps a copy in this tab's memory. A small panel shows how many posts it has
// seen. "Save file" downloads everything kept so far as one JSON file.
//
// The script sends no requests of its own, loads no other code, never scrolls or
// clicks, and changes nothing on the page apart from adding the panel. Requests that are not
// Bookmarks pass through untouched. Closing or reloading the tab discards what it kept.

(() => {
  "use strict";
  if (window.__xBookmarksCapture) {
    console.log("Bookmarks capture is already running in this tab.");
    return;
  }

  const pages = []; // one {cursor, status, body} per Bookmarks response, in arrival order
  const seen = new Set(); // post ids seen so far, for the counter
  let firstPage = false; // the first page is the request without a cursor
  const bottoms = new Set(); // the "next page" cursors X has handed out
  const gaps = new Map(); // cursor -> status, for failed requests that no retry has answered yet
  let ended = false; // true once X answers a "next page" request with an empty page
  let lastNew = null;
  let lastAdded = null;
  let panel = null;
  let line = null;

  const parse = (url) => {
    try {
      return new URL(url, location.href);
    } catch {
      return null;
    }
  };
  const isBookmarks = (url) => /\/graphql\/[^/]+\/Bookmarks$/.test(parse(url)?.pathname ?? "");
  const cursorOf = (url) => {
    try {
      const cursor = JSON.parse(parse(url).searchParams.get("variables") || "{}").cursor;
      return typeof cursor === "string" ? cursor : null;
    } catch {
      return null;
    }
  };

  // scan() finds three things in a response. Each bookmarked post is a timeline entry
  // ("tweet-<id>") holding tweet_results. The "Bottom" cursor is what X asks for the next page
  // with. An "instructions" list shows the answer is a real timeline. backlog.py reads saved
  // files with the same rules, so its counts match the panel's.
  const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
  const scan = (node, out = { ids: [], bottoms: [], timeline: false }) => {
    if (Array.isArray(node)) node.forEach((n) => scan(n, out));
    else if (isObject(node)) {
      if (typeof node.entryId === "string" && isObject(node.content?.itemContent?.tweet_results)) {
        out.ids.push(node.entryId.replace(/^tweet-/, ""));
        return out;
      }
      if (node.cursorType === "Bottom" && typeof node.value === "string") out.bottoms.push(node.value);
      if (Array.isArray(node.instructions)) out.timeline = true;
      Object.values(node).forEach((v) => scan(v, out));
    }
    return out;
  };

  const record = (url, status, text) => {
    let body = null;
    try {
      body = JSON.parse(text);
    } catch {}
    const cursor = cursorOf(url);
    pages.push({ cursor, status, body: body ?? String(text).slice(0, 2000) });
    const found = isObject(body) && isObject(body.data) ? scan(body) : null;
    const errors = Array.isArray(body?.errors) && body.errors.length > 0;
    if (status !== 200 || !found || (errors && !found.ids.length)) {
      gaps.delete(cursor); // re-added last, so the panel shows the newest failure's status
      gaps.set(cursor, status);
      return show();
    }
    gaps.delete(cursor); // a retry of the same page filled the gap
    if (cursor === null) firstPage = true;
    const fresh = found.ids.filter((id) => !seen.has(id));
    if (cursor !== null && bottoms.has(cursor) && found.timeline && !found.ids.length) ended = true;
    else if (fresh.length) ended = false; // more posts after an "end" (it was not the end)
    found.bottoms.forEach((c) => bottoms.add(c));
    fresh.forEach((id) => seen.add(id));
    if (fresh.length) lastNew = new Date();
    lastAdded = fresh.length;
    show();
  };

  // X's page fetches its data with XMLHttpRequest; fetch is covered too, in case that changes.
  const open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    if (isBookmarks(String(url))) {
      this.addEventListener("load", () => {
        const text = this.responseType === "json" ? JSON.stringify(this.response) : this.responseText;
        record(String(url), this.status, text);
      });
    }
    return open.call(this, method, url, ...rest);
  };
  const realFetch = window.fetch;
  window.fetch = function (input, init) {
    const result = realFetch.apply(this, arguments);
    const url = typeof input === "string" ? input : input?.url ?? String(input);
    if (isBookmarks(url)) {
      result.then((r) => r.clone().text().then((t) => record(url, r.status, t))).catch(() => {});
    }
    return result;
  };

  const save = () => {
    const link = document.querySelector('a[data-testid="AppTabBar_Profile_Link"]');
    const guess = (link?.getAttribute("href") || "").replace(/^\//, "");
    const answer = prompt("Which account are these bookmarks from? Your handle, without @:", guess);
    if (answer === null) return;
    const account = answer.trim().replace(/^@/, "");
    if (!/^[A-Za-z0-9_]{1,15}$/.test(account)) {
      alert("That is not an X handle (letters, digits and _, up to 15). Nothing was saved.");
      return;
    }
    const file = {
      format: "tech-digest/x-bookmarks-capture",
      version: 1,
      account,
      saved_at: new Date().toISOString(),
      posts_seen: seen.size,
      first_page: firstPage,
      reached_end: ended,
      pages,
    };
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(file)], { type: "application/json" }));
    a.download = `x-bookmarks-${account}-${new Date().toLocaleDateString("sv-SE")}.json`; // YYYY-MM-DD
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 60000);
  };

  const show = () => {
    if (!panel && document.body) {
      panel = document.createElement("div");
      panel.style.cssText =
        "position:fixed;right:12px;top:12px;z-index:2147483647;max-width:360px;padding:10px 12px;" +
        "background:#111;color:#fff;border:2px solid #1d9bf0;border-radius:8px;" +
        "font:13px/1.4 system-ui,sans-serif;white-space:pre-line";
      line = document.createElement("div");
      const button = document.createElement("button");
      button.textContent = "Save file";
      button.style.cssText = "margin-top:8px;padding:4px 10px;font:inherit;cursor:pointer";
      button.addEventListener("click", save);
      panel.append(line, button);
      document.body.append(panel);
    }
    if (!line) return;
    const rows = [`Bookmarks capture has ${seen.size} posts from ${pages.length} pages.`];
    if (!pages.length) rows.push("It is waiting for X to load your bookmarks.");
    else rows.push(firstPage ? "The first page was captured." : "The first page was missed, so see the instructions.");
    if (ended) rows.push("X returned an empty page, so this is the end of what X will show.");
    else if (lastAdded !== null) {
      const at = lastNew ? `, and the last new one came at ${lastNew.toLocaleTimeString()}` : "";
      rows.push(`The last page added ${lastAdded} new posts${at}.`);
    }
    if (gaps.size) {
      const status = [...gaps.values()].pop();
      const pagesFailed = gaps.size === 1 ? "1 page" : `${gaps.size} pages`;
      rows.push(`${pagesFailed} failed (status ${status}) and did not load since. Stop, wait, then scroll again.`);
    }
    line.textContent = rows.join("\n");
  };

  window.__xBookmarksCapture = { pages, save, count: () => seen.size };
  if (document.body) show();
  else document.addEventListener("DOMContentLoaded", show);
  console.log("Bookmarks capture is running. Scroll your bookmarks by hand; press Save file when done.");
})();
