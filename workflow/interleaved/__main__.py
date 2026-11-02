"""Stable command-line entry point for the interleaved product."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from workflow.interleaved.project import validate_project_files
from workflow.interleaved.runtime import ANSWER_SOURCE_ENV, ROOT, ProjectContext


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m workflow.interleaved",
        description="Run outer/inner Shannon proof construction for one project contract.",
    )
    parser.add_argument("--project")
    args, runner_args = parser.parse_known_args(argv)
    if not args.project:
        parser.error("--project is required")
    project_rel = Path(args.project)
    if project_rel.is_absolute() or ".." in project_rel.parts:
        parser.error("--project must be repository-relative")
    if not (ROOT / project_rel).resolve().is_file():
        parser.error(f"project contract does not exist: {project_rel}")
    try:
        context = ProjectContext.load(
            project_rel,
            answer_source=os.environ.get(ANSWER_SOURCE_ENV, "").strip() or None,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    errors = validate_project_files(context.root, context.project)
    if errors:
        parser.error("; ".join(errors))
    from workflow.interleaved.runner import main as run

    return run(runner_args, context=context)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
