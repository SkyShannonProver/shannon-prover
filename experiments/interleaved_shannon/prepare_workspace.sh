#!/usr/bin/env bash
# Create a clean detached sparse worktree for one official run.
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
REPO=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)
COMMIT=${1:-HEAD}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
WT=${2:-$REPO/.worktrees/interleaved-chacha-official-$STAMP}

COMMIT=$(git -C "$REPO" rev-parse --verify "$COMMIT^{commit}")

if [[ -e "$WT" ]]; then
  printf '%s\n' "refusing to overwrite existing path: $WT" >&2
  exit 2
fi

mkdir -p "$(dirname -- "$WT")"
git -C "$REPO" worktree add --detach "$WT" "$COMMIT"

git -C "$WT" sparse-checkout init --no-cone
git -C "$WT" sparse-checkout set --no-cone \
  '/core/' \
  '/workflow/' \
  '/tools/' \
  '/easycrypt-src/' \
  '/experiments/interleaved_shannon/' \
  '/AGENTS.md' \
  '/CLAUDE.md' \
  '/README.md' \
  '/pyproject.toml' \
  '/uv.lock' \
  '/.python-version' \
  '/.gitignore' \
  '/.gitattributes' \
  '/LICENSE' \
  '/CITATION.cff'

cd "$WT"
if command -v uv >/dev/null 2>&1; then
  uv sync -q
  PYTHON_RUN=(uv run python)
elif [[ -x "$REPO/.venv/bin/python" ]]; then
  # Managed runners may provide the repository environment without installing
  # the uv launcher itself. Reuse that exact verified environment in the fresh
  # ignored worktree rather than failing before experiment preflight.
  ln -s "$REPO/.venv" "$WT/.venv"
  PYTHON_RUN=("$WT/.venv/bin/python")
else
  printf '%s\n' \
    "neither uv nor a repository .venv Python is available" >&2
  exit 4
fi
"${PYTHON_RUN[@]}" tools/bootstrap_easycrypt.py >/dev/null
"${PYTHON_RUN[@]}" tools/bootstrap_easycrypt.py --verify-only >/dev/null
"${PYTHON_RUN[@]}" experiments/interleaved_shannon/source_projection.py \
  --exclude-answer-sources
"${PYTHON_RUN[@]}" experiments/interleaved_shannon/verify_task.py \
  --preflight >/dev/null

if [[ -n "$(git status --porcelain=v1 --untracked-files=all)" ]]; then
  printf '%s\n' "prepared worktree is not clean: $WT" >&2
  git status --short
  exit 3
fi

printf '%s\n' "workspace ready: $WT"
printf '%s\n' "commit: $COMMIT"
