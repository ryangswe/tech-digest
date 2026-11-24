// Runs tools/x-bookmarks-capture.js against a fake browser, for tests/test_backlog.py.
//   node tests/capture_harness.js <capture.json>
// Replays each page of a synthetic capture file as X's Bookmarks request (by XMLHttpRequest,
// the last page by fetch), sends one unrelated request, presses Save, and prints JSON:
// {saved: <the saved file>, download, panel, other_seen, requests}.
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const source = fs.readFileSync(path.join(__dirname, "../tools/x-bookmarks-capture.js"), "utf8");
const fixture = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

let saved = null;
let download = null;
const requests = []; // what the page asked for; the script must add none of its own
const elements = [];

class FakeElement {
  constructor(tag) {
    this.tag = tag;
    this.style = {};
    this.children = [];
    this.listeners = {};
    this.textContent = "";
    elements.push(this);
  }
  append(...kids) { this.children.push(...kids); }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  click() {
    if (this.tag === "a") download = this.download;
    (this.listeners.click || []).forEach((fn) => fn());
  }
  remove() {}
  getAttribute(name) { return name === "href" ? "/acct_alpha" : null; }
}

class FakeXHR {
  constructor() { this.listeners = {}; this.responseType = ""; }
  open(method, url) { this.url = url; requests.push(url); }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  respond(status, text) {
    this.status = status;
    this.responseText = text;
    (this.listeners.load || []).forEach((fn) => fn());
  }
}

class FakeURL extends URL {
  static createObjectURL(blob) { saved = blob; return "blob:fake"; }
  static revokeObjectURL() {}
}

const sandbox = {
  console: { log() {} },
  location: { href: "https://x.com/i/bookmarks" },
  URL: FakeURL,
  Blob,
  XMLHttpRequest: FakeXHR,
  setTimeout() {},
  prompt: (_question, guess) => guess,
  alert() {},
  fetch: async (url) => {
    requests.push(String(url));
    const page = fixture.pages[fixture.pages.length - 1];
    return new Response(JSON.stringify(page.body), { status: page.status });
  },
  document: {
    body: new FakeElement("body"),
    createElement: (tag) => new FakeElement(tag),
    querySelector: () => new FakeElement("a"),
    addEventListener() {},
  },
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(source, sandbox);

const urlFor = (cursor) => {
  const variables = { count: 20, includePromotedContent: true, ...(cursor ? { cursor } : {}) };
  return `https://x.com/i/api/graphql/AbC123/Bookmarks?variables=${encodeURIComponent(JSON.stringify(variables))}`;
};

(async () => {
  const other = new sandbox.XMLHttpRequest();
  sandbox.XMLHttpRequest.prototype.open.call(other, "GET", "https://x.com/i/api/graphql/Q/HomeTimeline");
  other.respond(200, '{"data":{}}');
  const other_seen = sandbox.__xBookmarksCapture.pages.length;

  for (const page of fixture.pages.slice(0, -1)) {
    const xhr = new sandbox.XMLHttpRequest();
    sandbox.XMLHttpRequest.prototype.open.call(xhr, "GET", urlFor(page.cursor));
    xhr.respond(page.status, typeof page.body === "string" ? page.body : JSON.stringify(page.body));
  }
  const last = fixture.pages[fixture.pages.length - 1];
  await sandbox.fetch(urlFor(last.cursor));
  await new Promise((resolve) => setImmediate(resolve)); // let the clone be read

  const panelText = elements.filter((e) => e.tag === "div" && e.textContent).map((e) => e.textContent);
  elements.find((e) => e.tag === "button").click(); // Save file
  console.log(JSON.stringify({
    saved: saved ? JSON.parse(await saved.text()) : null,
    download,
    panel: panelText.join("\n"),
    other_seen,
    requests,
  }));
})();
