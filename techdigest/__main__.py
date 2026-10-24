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
    try:
        digest = build_digest(picks, cands, report, ranker=args.ranker)
    except RenderError as e:
        print(f"{args.picks} was refused ({len(e.errors)} problem(s)):", file=sys.stderr)
        for err in e.errors:
            print(f"  - {err}", file=sys.stderr)
        print("Fix the picks file and run render again.", file=sys.stderr)
        return 2
    j, m = write_digest(digest, Path(args.out))
    print(f"wrote {m} and {j}")
    return 0


def cmd_mark_seen(args) -> int:
    from .fetch import mark_seen
    day = json.loads(Path(args.candidates).read_text(encoding="utf-8"))["date"]
    added, pruned = mark_seen(state_dir=Path(args.state), candidates_path=Path(args.candidates),
                              today=day)
    print(f"seen: +{added} new, -{pruned} pruned (older than 60 days)")
    return 0


def cmd_status(args) -> int:
    from .feedback import load_lines, weekly_status
    today = _today(args)
    weekly_path = Path(args.state) / "weekly.json"
    weekly = json.loads(weekly_path.read_text()) if weekly_path.exists() else {}
    due, reason = weekly_status(today, weekly, load_lines(Path(args.state) / "feedback.jsonl"))
    print(json.dumps({"date": today, "branch": f"claude/digest-{today}",
                      "weekly_review_due": due, "reason": reason}, indent=1))
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
    s.set_defaults(func=cmd_render)

    s = sub.add_parser("mark-seen", help="add every candidate to state/seen.json and prune")
    s.add_argument("--state", default="state")
    s.add_argument("--candidates", default="build/candidates.json")
    s.set_defaults(func=cmd_mark_seen)

    s = sub.add_parser("status", help="today's date, branch name and whether the weekly review is due")
    s.add_argument("--state", default="state")
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
