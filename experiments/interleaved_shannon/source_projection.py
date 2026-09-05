#!/usr/bin/env python3
"""Keep answer-bearing EasyCrypt examples absent from experiment worktrees."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANSWER_SOURCE = ROOT / "easycrypt-src" / "examples" / "ChaChaPoly" / "chacha_poly.ec"

BASE_PATTERNS = (
    "/core/",
    "/workflow/",
    "/tools/",
    "/easycrypt-src/",
    "/experiments/interleaved_shannon/",
    "/AGENTS.md",
    "/CLAUDE.md",
    "/README.md",
    "/pyproject.toml",
    "/uv.lock",
    "/.python-version",
    "/.gitignore",
    "/.gitattributes",
    "/LICENSE",
    "/CITATION.cff",
)
CONFINED_PATTERNS = BASE_PATTERNS[:4] + ("!/easycrypt-src/examples/",) + BASE_PATTERNS[4:]


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def sparse_checkout_enabled() -> bool:
    result = _git("config", "--bool", "core.sparseCheckout")
    return result.returncode == 0 and result.stdout.strip() == "true"


def _set_patterns(patterns: tuple[str, ...]) -> None:
    result = _git("sparse-checkout", "set", "--no-cone", *patterns)
    if result.returncode != 0:
        raise RuntimeError("sparse checkout update failed: " + result.stderr.strip())


def exclude_answer_sources() -> None:
    if sparse_checkout_enabled():
        _set_patterns(CONFINED_PATTERNS)
        if ANSWER_SOURCE.exists():
            raise RuntimeError(f"answer-bearing source remains visible: {ANSWER_SOURCE}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exclude-answer-sources", action="store_true", required=True)
    parser.parse_args()
    exclude_answer_sources()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
