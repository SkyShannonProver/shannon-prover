#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
REPO=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)
cd "$REPO"
if command -v uv >/dev/null 2>&1; then
  exec uv run python experiments/interleaved_shannon/run_experiment.py "$@"
fi
if [[ -x "$REPO/.venv/bin/python" ]]; then
  exec "$REPO/.venv/bin/python" \
    experiments/interleaved_shannon/run_experiment.py "$@"
fi
printf '%s\n' "neither uv nor .venv/bin/python is available" >&2
exit 4
