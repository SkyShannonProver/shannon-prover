#!/usr/bin/env bash
# Start the Shannon Prover playground locally.
# Run this in a NORMAL terminal (not under an OS sandbox) so EasyCrypt / why3 can
# start. Keep the terminal open while you play; press Ctrl+C to stop.
# Then open http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")/.."
eval "$(opam env --switch=easycrypt)"
exec uv run --with fastapi --with "uvicorn[standard]" \
    uvicorn playground.server:app --host 127.0.0.1 --port "${PORT:-8000}"
