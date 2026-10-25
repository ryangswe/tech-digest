"""Command line: python3 -m techdigest <command>. See prompts/daily.md for the daily order."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import ConfigError, load_config
from .text import local_now, parse_date


def _now(arg: str | None) -> datetime:
    if not arg:
        return datetime.now(timezone.utc)
    dt = parse_date(arg)
    if not dt:
        sys.exit(f"--now: cannot parse {arg!r}")
    return dt


def _today(args) -> str:
    if getattr(args, "date", None):
        return args.date
    tz = load_config(args.config).timezone
    return local_now(tz, _now(getattr(args, "now", None))).date().isoformat()


def cmd_fetch(args) -> int:
    from .fetch import run_fetch
    from .net import fixture_getter
    cfg = load_config(args.config)
    getter = fixture_getter(Path(args.fixtures)) if args.fixtures else None
    run_fetch(cfg, state_dir=Path(args.state), out_dir=Path(args.out), now=_now(args.now),
              getter=getter)
    return 0


def cmd_render(args) -> int:
    from .render import RenderError, build_digest, load_json, write_digest
    cands = load_json(Path(args.candidates))
    report = load_json(Path(args.report)) if Path(args.report).exists() else {}
    try:
        picks = load_json(Path(args.picks))
    except json.JSONDecodeError as e:
        print(f"{args.picks}: invalid JSON at line {e.lineno}: {e.msg}", file=sys.stderr)
        return 2
    cards = load_json(Path(args.cards)) if Path(args.cards).exists() else []
    try:
        digest = build_digest(picks, cands, report, ranker=args.ranker, cards=cards)
    except RenderError as e:
        print(f"{args.picks} was refused ({len(e.errors)} problem(s)):", file=sys.stderr)
        for err in e.errors:
            print(f"  - {err}", file=sys.stderr)
        print("Fix the picks file and run render again.", file=sys.stderr)
        return 2
    j, m = write_digest(digest, Path(args.out))
    print(f"wrote {m} and {j}")
    return 0


def _item_fields(c: dict) -> dict:
    return {k: c.get(k, "") for k in ("title", "url", "source", "source_name", "link_name", "summary")}


def cmd_read(args) -> int:
    from .net import http_get
    from .read import read_many
    items: dict[str, dict] = {}
    if args.ids:
        cands = {c["id"]: c for c in json.loads(Path(args.candidates).read_text(encoding="utf-8"))["candidates"]}
        ids = [i for i in args.ids.split(",") if i]
        missing = [i for i in ids if i not in cands]
        if missing:
            print(f"unknown candidate id(s): {', '.join(missing)}", file=sys.stderr)
            return 2
        items.update({i: _item_fields(cands[i]) for i in ids})
    if args.items:  # e.g. build/dig.json from dig-requests: [{id, url, title, ...}]
        for it in json.loads(Path(args.items).read_text(encoding="utf-8")):
            items[it["id"]] = {**_item_fields(it), "asked": True}
    if not items:
        print("nothing to read: pass --ids and/or --items", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    old = json.loads((out / "items.json").read_text()) if (out / "items.json").exists() else {}
    (out / "items.json").write_text(json.dumps({**old, **items}, indent=1, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
    if args.fixtures:
        urlmap = json.loads((Path(args.fixtures) / "urls.json").read_text())

        def getter(url):
            if url not in urlmap:
                raise RuntimeError("no fixture")
            return (Path(args.fixtures) / urlmap[url]).read_bytes()
    else:
        cfg = load_config(args.config)

        def getter(url):
            return http_get(url, cfg.user_agent, cfg.request_timeout)
    index = read_many([(i, it["url"]) for i, it in items.items()], out, getter)
    ok = sum(1 for i in items if index[i]["status"] == "ok")
    print(f"read {ok}/{len(items)} ok -> {out}/index.json (statuses only; the page texts are for "
          "the reader subagent, not for you)")
    return 0


def cmd_cards(args) -> int:
    from .cards import load_projects, validate_dir
    from .state import write_json
    items = json.loads((Path(args.reads) / "items.json").read_text(encoding="utf-8"))
    valid, errors = validate_dir(Path(args.cards_dir), items, load_projects(Path(args.profile)))
    for c in valid:
        c["asked"] = bool(items[c["id"]].get("asked"))
    write_json(Path(args.out), valid)
    missing = sorted(set(items) - {c["id"] for c in valid} - set(errors))
    print(f"{len(valid)} valid card(s) -> {args.out}")
    if missing:
        print(f"no card written for: {', '.join(missing)}")
    for cid, errs in errors.items():
        print(f"{cid}: refused", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
    return 2 if errors else 0


def cmd_mark_seen(args) -> int:
    from .fetch import mark_seen
    day = json.loads(Path(args.candidates).read_text(encoding="utf-8"))["date"]
    added, pruned = mark_seen(state_dir=Path(args.state), candidates_path=Path(args.candidates),
                              today=day)
    print(f"seen: +{added} keys (an item's URL and its discussion threads each count), "
          f"-{pruned} pruned (older than 60 days)")
    return 0


def cmd_status(args) -> int:
    from .feedback import load_lines, weekly_status
    today = _today(args)
    weekly_path = Path(args.state) / "weekly.json"
    weekly = json.loads(weekly_path.read_text()) if weekly_path.exists() else {}
    due, reason = weekly_status(today, weekly, load_lines(Path(args.state) / "feedback.jsonl"))
    delivered = (Path(args.digest_dir) / f"{today}.md").exists()
    print(json.dumps({"date": today, "branch": f"claude/digest-{today}",
                      "already_delivered": delivered,
                      "weekly_review_due": due and not delivered, "reason": reason}, indent=1))
    return 0


def cmd_weekly_done(args) -> int:
    from .state import write_json
    write_json(Path(args.state) / "weekly.json", {"last_proposal": _today(args)})
    print(f"weekly review recorded for {_today(args)}")
    return 0


def cmd_feedback_summary(args) -> int:
    from .feedback import load_lines, summary
    print(summary(load_lines(Path(args.state) / "feedback.jsonl"), _today(args), args.days))
    return 0


def cmd_dry_run(args) -> int:
    from .dryrun import dry_run
    md = dry_run(Path(args.config), Path(args.fixtures), Path(args.out))
    if args.print:
        print(md.read_text(encoding="utf-8"))
    return 0


def cmd_integrate(args) -> int:
    from .integrate import IntegrateError, integrate
    try:
        result = integrate(Path("."), args.branch)
    except IntegrateError as e:
        print(f"integrate refused: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


def _gh():
    from .github import GitHub
    return GitHub()


def cmd_deliver(args) -> int:
    from . import deliver
    gh = _gh()
    if args.step == "harvest":
        lines = deliver.harvest(gh, Path("."), os.environ["GITHUB_REPOSITORY_OWNER"], args.date)
        print(f"harvested {len(lines)} feedback line(s)")
    else:
        print(json.dumps(deliver.publish(gh, Path("."), args.date)))
    return 0


def cmd_dig_requests(args) -> int:
    """Read 🔍 ticks from the open digest issue with `gh api` (authenticated by the cloud proxy)."""
    import subprocess
    from .deliver import DIGEST_LABEL, dig_requests
    from .state import write_json
    repo = args.repo or json.loads(Path(args.config).read_text()).get("repository", "")
    r = subprocess.run(["gh", "api", f"repos/{repo}/issues?labels={DIGEST_LABEL}&state=open&per_page=20"],
                       capture_output=True, text=True)
    if r.returncode:
        print(f"gh api failed ({r.stderr.strip()[:200]}); no 🔍 requests today", file=sys.stderr)
        write_json(Path(args.out), [])
        return 0
    issues = [i for i in json.loads(r.stdout) if "pull_request" not in i]
    reqs = dig_requests(issues, Path("."))
    write_json(Path(args.out), reqs)
    print(f"{len(reqs)} 🔍 request(s) -> {args.out}")
    return 0


def cmd_weekly(args) -> int:
    from . import weekly
    fn = weekly.prepare if args.step == "prepare" else weekly.publish
    print(json.dumps(fn(_gh(), Path("."), args.date)))
    return 0


def cmd_backlog(args) -> int:
    from . import backlog as B
    root = Path(args.root)
    try:
        if args.step == "import":
            if not args.path:
                print("backlog import needs the archive path (zip or unzipped folder)", file=sys.stderr)
                return 2
            stats = B.import_archive(Path(args.path), root)
            print(json.dumps(stats, indent=1))
            return 3 if stats.get("warning") else 0
        if args.step == "read":
            from .net import http_get
            from .read import read_many
            cfg = load_config(args.config)
            items = json.loads((root / "raw/items.json").read_text(encoding="utf-8"))
            todo = [(i, it["url"]) for i, it in items.items() if it["url"] != it["post_url"]]
            index = read_many(todo, root / "raw/reads", lambda u: http_get(u, cfg.user_agent, cfg.request_timeout),
                              log=lambda *a: None)
            print(json.dumps(dict(__import__("collections").Counter(e["status"] for e in index.values()))))
            return 0
        if args.step == "batches":
            paths = B.make_batches(root, args.size)
            print(f"{len(paths)} batch(es) of up to {args.size} -> {root}/raw/batches/")
            return 0
        if args.step == "validate":
            report = B.validate_all(root, Path(args.profile))
            bad = {k: v for k, v in report.items() if v}
            print(f"{len(report) - len(bad)}/{len(report)} batch(es) valid")
            for name, errs in bad.items():
                print(f"{name}:", file=sys.stderr)
                for e in errs[:20]:
                    print(f"  - {e}", file=sys.stderr)
            return 2 if bad else 0
        if args.step == "report":
            from .state import write_json
            bad = {k: v for k, v in B.validate_all(root, Path(args.profile)).items() if v}
            if bad:
                print(f"refusing to report: {len(bad)} batch(es) not valid yet (run backlog validate)", file=sys.stderr)
                return 2
            md, queue = B.build_report(root)
            out = root / "out"
            out.mkdir(parents=True, exist_ok=True)
            (out / "summary.md").write_text(md, encoding="utf-8")
            write_json(out / "queue.json", queue)
            print(f"wrote {out}/summary.md and {out}/queue.json ({len(queue)} cards queued)")
            return 0
    except B.BacklogError as e:
        print(f"backlog: {e}", file=sys.stderr)
        return 2
    return 2


def cmd_report_failure(args) -> int:
    from .deliver import report_failure
    body = Path(args.body_file).read_text(encoding="utf-8", errors="replace") if args.body_file else ""
    print(report_failure(_gh(), args.title, body))
    return 0


def cmd_check_delivered(args) -> int:
    from .deliver import check_delivered
    print(check_delivered(_gh(), Path("."), _today(args)))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m techdigest", description=__doc__)
    p.add_argument("--config", default="sources.json")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("fetch", help="fetch all sources into build/candidates.json")
    s.add_argument("--state", default="state")
    s.add_argument("--out", default="build")
    s.add_argument("--fixtures", help="read fixtures/<source-id>.* instead of the network")
    s.add_argument("--now", help="pretend it is this time (ISO 8601)")
    s.set_defaults(func=cmd_fetch)

    s = sub.add_parser("render", help="validate build/picks.json and write digest/DATE.{md,json}")
    s.add_argument("--picks", default="build/picks.json")
    s.add_argument("--candidates", default="build/candidates.json")
    s.add_argument("--report", default="build/fetch-report.json")
    s.add_argument("--out", default="digest")
    s.add_argument("--ranker", default="claude", choices=["claude", "keywords"])
    s.add_argument("--cards", default="build/cards.json", help="validated cards (optional)")
    s.set_defaults(func=cmd_render)

    s = sub.add_parser("read", help="fetch full text of candidates into build/reads/ (for the reader subagent)")
    s.add_argument("--ids", help="comma-separated candidate ids")
    s.add_argument("--items", help="JSON list of {id, url, title, ...} (from dig-requests)")
    s.add_argument("--candidates", default="build/candidates.json")
    s.add_argument("--out", default="build/reads")
    s.add_argument("--fixtures", help="read pages from DIR/urls.json instead of the network")
    s.set_defaults(func=cmd_read)

    s = sub.add_parser("cards", help="validate the reader's build/cards/*.json into build/cards.json")
    s.add_argument("--reads", default="build/reads")
    s.add_argument("--cards-dir", default="build/cards")
    s.add_argument("--profile", default="profile.md")
    s.add_argument("--out", default="build/cards.json")
    s.set_defaults(func=cmd_cards)

    s = sub.add_parser("mark-seen", help="add every candidate to state/seen.json and prune")
    s.add_argument("--state", default="state")
    s.add_argument("--candidates", default="build/candidates.json")
    s.set_defaults(func=cmd_mark_seen)

    s = sub.add_parser("status", help="today's date, branch name and whether the weekly review is due")
    s.add_argument("--state", default="state")
    s.add_argument("--digest-dir", default="digest")
    s.add_argument("--now")
    s.add_argument("--date")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("weekly-done", help="record that the weekly interests PR was opened today")
    s.add_argument("--state", default="state")
    s.add_argument("--date")
    s.set_defaults(func=cmd_weekly_done)

    s = sub.add_parser("feedback-summary", help="recent 👍/👎 and comments, for the ranking step")
    s.add_argument("--state", default="state")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--date")
    s.set_defaults(func=cmd_feedback_summary)

    s = sub.add_parser("dry-run", help="offline run from fixtures into build/dry-run/")
    s.add_argument("--fixtures", default="fixtures")
    s.add_argument("--out", default="build/dry-run")
    s.add_argument("--print", action="store_true", help="print the digest")
    s.set_defaults(func=cmd_dry_run)

    s = sub.add_parser("integrate", help="(Action) copy a claude/digest-* branch's output into main")
    s.add_argument("--branch", required=True)
    s.set_defaults(func=cmd_integrate)

    s = sub.add_parser("deliver", help="(Action) harvest feedback, or publish today's issue")
    s.add_argument("step", choices=["harvest", "publish"])
    s.add_argument("--date", required=True)
    s.set_defaults(func=cmd_deliver)

    s = sub.add_parser("dig-requests", help="items you ticked 🔍 on the open digest issue -> build/dig.json")
    s.add_argument("--repo", help="owner/name (default: sources.json `repository`)")
    s.add_argument("--out", default="build/dig.json")
    s.set_defaults(func=cmd_dig_requests)

    s = sub.add_parser("weekly", help="(Action, Mondays) build or publish the weekly Try-this issue")
    s.add_argument("step", choices=["prepare", "publish"])
    s.add_argument("--date", required=True)
    s.set_defaults(func=cmd_weekly)

    s = sub.add_parser("backlog", help="(local, one-off) import and triage the X bookmark backlog")
    s.add_argument("step", choices=["import", "read", "batches", "validate", "report"])
    s.add_argument("path", nargs="?", help="import: the X archive (.zip or unzipped folder)")
    s.add_argument("--root", default="backlog")
    s.add_argument("--size", type=int, default=40)
    s.add_argument("--profile", default="profile.md")
    s.set_defaults(func=cmd_backlog)

    s = sub.add_parser("report-failure", help="(Action) open a failure issue once per title")
    s.add_argument("--title", required=True)
    s.add_argument("--body-file")
    s.set_defaults(func=cmd_report_failure)

    s = sub.add_parser("check-delivered", help="(Action) open an issue if today's digest is missing")
    s.add_argument("--date")
    s.set_defaults(func=cmd_check_delivered)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
