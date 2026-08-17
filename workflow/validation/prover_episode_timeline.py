"""Build proof-transition episode timelines from replay artifacts.

Each timeline step comes from the TacticExecutionResult bound to one proof
interaction. Its embedded ProverWorkspaceView supplies the authoritative goal
and status after that interaction; action selection is not duplicated here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from core.easycrypt.session_episode_timeline import build_session_episode_timeline
from workflow.validation.replay_artifacts import (
    ReplayArtifact,
    iter_replay_artifacts,
)


TIMELINE_SCHEMA_VERSION = 1
TIMELINE_KIND = "prover_episode_timeline"


def build_episode_timeline(artifact: ReplayArtifact) -> dict[str, Any]:
    session_timeline = build_session_episode_timeline(artifact.proof_dir)

    return {
        "schema_version": TIMELINE_SCHEMA_VERSION,
        "kind": TIMELINE_KIND,
        "proof_id": artifact.summary.proof_id,
        "file": artifact.summary.file,
        "lemma": artifact.summary.lemma,
        "outcome": artifact.summary.outcome,
        "ok": bool(session_timeline.get("ok")),
        "source": session_timeline.get("source"),
        "step_count": _int(session_timeline.get("step_count")),
        "rollup": session_timeline.get("rollup") or {},
        "steps": session_timeline.get("steps") or [],
        "notes": session_timeline.get("notes") or [],
        "errors": session_timeline.get("errors") or [],
    }


def build_replay_root_timelines(root: Path) -> dict[str, Any]:
    timelines = [build_episode_timeline(a) for a in iter_replay_artifacts(root)]
    return {
        "schema_version": TIMELINE_SCHEMA_VERSION,
        "kind": "prover_episode_timeline_report",
        "artifact_root": str(Path(root).resolve()),
        "proof_count": len(timelines),
        "step_count": sum(_int(t.get("step_count")) for t in timelines),
        "timelines": timelines,
    }


def write_report(root: Path, report: dict[str, Any]) -> Path:
    path = Path(root) / "prover_episode_timelines.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact-root", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write-report", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.artifact_root)
    report = build_replay_root_timelines(root)
    if not args.no_write_report:
        write_report(root, report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            "PROVER-EPISODE-TIMELINE: "
            f"proofs={report['proof_count']} steps={report['step_count']}"
        )
        for timeline in report["timelines"]:
            rollup = timeline.get("rollup") or {}
            print(
                f"- {timeline.get('lemma')}: steps={timeline.get('step_count')} "
                f"final={rollup.get('final_proof_status')} "
                f"notes={len(timeline.get('notes') or [])}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
