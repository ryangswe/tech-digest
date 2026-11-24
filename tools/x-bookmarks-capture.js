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
// Read this file in full before you run it; it is all the code there is. How to use it:
// docs/x-bookmarks.md. Paste it into the browser console on x.com, or install it as a local
// userscript (the header above).
//
// What it does: X's Bookmarks page asks X's servers for your bookmarks a page at a time, as you
// scroll. This script listens for the answers to those requests (the "Bookmarks" GraphQL
// request) and keeps a copy in this tab's memory. A small panel shows how many posts it has
// seen. "Save file" downloads everything kept so far as one JSON file.
//
// What it does not do: it sends no requests of its own, loads no other code, never scrolls or
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
  let failed = 0;
  let lastNew = null;
  let lastAdded = null;
  let lastStatus = null;
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
      return JSON.parse(parse(url).searchParams.get("variables") || "{}").cursor ?? null;
    } catch {
      return null;
    }
  };

  // Post ids in a response: each bookmarked post is a timeline entry ("tweet-<id>") that holds
  // tweet_results; cursors and other entries don't.
  const postIds = (node, out = []) => {
    if (Array.isArray(node)) node.forEach((n) => postIds(n, out));
    else if (node && typeof node === "object") {
      if (typeof node.entryId === "string" && node.content?.itemContent?.tweet_results) {
        out.push(node.entryId.replace(/^tweet-/, ""));
      } else Object.values(node).forEach((v) => postIds(v, out));
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
    const ok = status === 200 && body && body.data;
    if (!ok) failed += 1;
    if (ok && cursor === null) firstPage = true;
    const fresh = ok ? postIds(body).filter((id) => !seen.has(id)) : [];
    fresh.forEach((id) => seen.add(id));
    if (fresh.length) lastNew = new Date();
    lastAdded = ok ? fresh.length : null;
    lastStatus = status;
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
        "position:fixed;left:12px;bottom:12px;z-index:2147483647;max-width:360px;padding:10px 12px;" +
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
    const rows = [`Bookmarks capture: ${seen.size} posts from ${pages.length} pages`];
    if (!pages.length) rows.push("Waiting for X to load your bookmarks…");
    else rows.push(firstPage ? "First page: captured" : "First page: missed (see the instructions)");
    if (lastAdded !== null) {
      const at = lastNew ? `, last new post at ${lastNew.toLocaleTimeString()}` : "";
      rows.push(`Last page added ${lastAdded}${lastAdded === 0 ? " (this may be the end)" : ""}${at}`);
    }
    if (failed) rows.push(`Failed responses: ${failed} (last status ${lastStatus}). Stop and wait.`);
    line.textContent = rows.join("\n");
  };

  window.__xBookmarksCapture = { pages, save, count: () => seen.size };
  if (document.body) show();
  else document.addEventListener("DOMContentLoaded", show);
  console.log("Bookmarks capture is running. Scroll your bookmarks by hand; press Save file when done.");
})();
