# Shannon Prover Playground

A browser surface that lets a human drive an EasyCrypt proof the same way the agent
does — sending one JSON intent at a time to the **same**
`ProofNodeManager.handle_agent_message` loop, and reading the **same** followup the
agent reads. Toggle **L1 (raw EC)** vs **L4 (compiler surface)** live and watch the
right panel change.

```
browser ──{intent}──▶ WS server ──▶ ProofNodeManager.handle_agent_message(json)
                                          │   (= the call the agent makes)
                                          ▼
                                     EasyCrypt runs/probes one tactic
browser ◀─{followup_md + view}── WS server ◀── ManagedTurn{ok, workspace_view, …}
```

## Run it locally

Prerequisites: the project's `uv` env, and the EasyCrypt opam switch (`easycrypt`).
Run in a **normal terminal** (not under an OS sandbox) so EasyCrypt/why3 can start —
the same requirement as any EasyCrypt run here (the sandbox blocks `nice()`, which
`why3server` needs for `smt()`).

From the repository root:

```bash
eval "$(opam env --switch=easycrypt)"
uv run --with fastapi --with "uvicorn[standard]" \
    uvicorn playground.server:app --host 127.0.0.1 --port 8000
```

Then open <http://127.0.0.1:8000>.

(Or install the two deps once — `uv pip install -r playground/requirements.txt` — and
drop the `--with` flags.)

## Use it

1. Pick the target file + lemma (defaults:
   `eval/examples/ChaChaPoly/chacha_poly.ec` · `step4_1`),
   pick **L1** or **L4**, click **Start**.
2. Type a tactic in the box: **Enter** = `commit_tactic`.
   Or use the surfaced context-topic buttons, `lookup…`, and the header
   `undo` / `restart` / `finish`.
3. The right panel shows **what the agent reads** — the rendered followup. Flip the
   `followup ▸ audit view` toggle to see the raw `ProverWorkspaceView` JSON (the
   off-surface audit twin). Flip **L1 ⇄ L4** to feel the difference: L1 collapses to
   the goal + a one-line accept/reject; L4 adds the workbench, candidate moves, and
   inspect handles.

Notes:
- Structural tactics (`proc.`, `inline*.`, `call (_: …).`, `wp`, rewrites) work
  immediately. `smt()` / `auto` need why3, which EasyCrypt starts automatically when
  the process is not sandboxed.
- Each session spawns its own EasyCrypt process; `PLAYGROUND_MAX_SESSIONS` (default 4)
  caps concurrency. Sessions are disposed on disconnect.
- Don't run this while an `eval_suite` prover run is using EasyCrypt in the **same**
  worktree (session-dir contention) — use a separate worktree or wait for it to finish.

## Files

- `node_boot.py` — bootstraps one `ProofNodeManager`, drives a turn, renders the
  followup. The whole proof engine is reused; this is just the adapter.
- `server.py` — FastAPI + WebSocket; one session per connection, blocking EC calls
  run in a threadpool.
- `static/index.html` — the UI (vanilla JS, no build step).

## Run your own web playground

There is no hosted instance — the playground is **self-serve**: anyone with the
repo + the EasyCrypt opam switch runs their own web UI with the two commands in
"Run it locally" above. That's the whole setup; the server is a single FastAPI
process with no external services, database, or build step.

Notes if you share it beyond your own browser (e.g. with your lab over LAN):

- Bind to your LAN address instead of `127.0.0.1` (e.g. `--host 0.0.0.0`) — but
  only on a network you trust: sessions run a real EasyCrypt process, and there
  is no auth layer.
- `PLAYGROUND_MAX_SESSIONS` (default 4) caps concurrent EC sessions; each one
  costs a CPU core + a few hundred MB while active.
- Sessions are disposed on disconnect, so an abandoned tab frees its EasyCrypt
  process.
