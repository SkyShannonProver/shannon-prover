"""Stable command-line entry point for the interleaved product."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from workflow.interleaved.project import InterleavedProject, PROJECT_ENV, validate_project_files


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m workflow.interleaved",
        description="Run outer/inner Shannon proof construction for one project contract.",
    )
    parser.add_argument("--project")
    args, runner_args = parser.parse_known_args()
    if not args.project:
        parser.error("--project is required")
    project_rel = Path(args.project)
    if project_rel.is_absolute() or ".." in project_rel.parts:
        parser.error("--project must be repository-relative")
    project_path = (ROOT / project_rel).resolve()
    if not project_path.is_file():
        parser.error(f"project contract does not exist: {project_rel}")
    try:
        project = InterleavedProject.load(project_path)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    errors = validate_project_files(ROOT, project)
    if errors:
        parser.error("; ".join(errors))
    os.environ[PROJECT_ENV] = project_rel.as_posix()
    sys.argv = [sys.argv[0], *runner_args]
    from workflow.interleaved.runner import main as run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
