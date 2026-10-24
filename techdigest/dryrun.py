"""Offline end-to-end run: fixtures -> fetch -> keyword picks -> render. Never touches state/."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .config import load_config
from .fetch import mark_seen, run_fetch
from .net import fixture_getter
from .rank_keywords import keyword_picks
from .render import build_digest, write_digest
from .state import write_json
from .text import parse_date


def dry_run(config_path: Path = Path("sources.json"), fixtures: Path = Path("fixtures"),
            out: Path = Path("build/dry-run"), log=print) -> Path:
    cfg = load_config(config_path)
    fixtures, out = Path(fixtures), Path(out)
    now = parse_date((fixtures / "now.txt").read_text().strip())
    if out.exists():
        shutil.rmtree(out)
    state = out / "state"
    shutil.copytree(fixtures / "state", state)
    report = run_fetch(cfg, state_dir=state, out_dir=out, now=now,
                       getter=fixture_getter(fixtures / "feeds"), log=log)
    cands = json.loads((out / "candidates.json").read_text(encoding="utf-8"))
    picks = keyword_picks(cands, cfg.dry_run_keywords)
    write_json(out / "picks.json", picks)
    digest = build_digest(picks, cands, report, ranker="keywords")
    _, md = write_digest(digest, out / "digest")
    mark_seen(state_dir=state, candidates_path=out / "candidates.json", today=cands["date"])
    log(f"dry run digest: {md}")
    return md
