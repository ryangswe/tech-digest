"""A minimal GitHub REST client (urllib), used only by the delivery Action."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


class GitHubError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status


class GitHub:
    def __init__(self, repo: str | None = None, token: str | None = None,
                 api: str = "https://api.github.com"):
        self.repo = repo or os.environ["GITHUB_REPOSITORY"]
        self.token = token or os.environ["GITHUB_TOKEN"]
        self.api = api

    def request(self, method: str, path: str, body: dict | None = None,
                params: dict | None = None):
        url = f"{self.api}/repos/{self.repo}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "tech-digest-deliver",
            **({"Content-Type": "application/json"} if data else {}),
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise GitHubError(e.code, e.read().decode(errors="replace")[:300])
        return json.loads(raw) if raw else None

    # The calls deliver.py needs; FakeGitHub in the tests implements the same methods.
    def list_issues(self, label: str, state: str = "open") -> list[dict]:
        out = self.request("GET", "/issues", params={"labels": label, "state": state,
                                                     "per_page": 100})
        return [i for i in out if "pull_request" not in i]

    def create_issue(self, title: str, body: str, labels: list[str]) -> dict:
        return self.request("POST", "/issues", {"title": title, "body": body, "labels": labels})

    def close_issue(self, number: int) -> None:
        self.request("PATCH", f"/issues/{number}", {"state": "closed", "state_reason": "completed"})

    def issue_reactions(self, number: int) -> list[dict]:
        return self.request("GET", f"/issues/{number}/reactions", params={"per_page": 100})

    def issue_comments(self, number: int) -> list[dict]:
        return self.request("GET", f"/issues/{number}/comments", params={"per_page": 100})

    def open_pulls(self) -> list[dict]:
        return self.request("GET", "/pulls", params={"state": "open", "per_page": 100})

    def ensure_label(self, name: str, color: str, description: str) -> None:
        try:
            self.request("GET", f"/labels/{urllib.parse.quote(name)}")
        except GitHubError as e:
            if e.status != 404:
                raise
            self.request("POST", "/labels", {"name": name, "color": color,
                                             "description": description})
