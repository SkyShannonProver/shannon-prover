# Shannon Prover: Claude entry point

`AGENTS.md` is the canonical repository, runtime, eval-safety, and testing
contract for every coding agent. Read it before making changes. This file adds
no alternate protocol or legacy Claude-specific proof surface.

## Current boundary

```text
orchestrator
  -> ProofNodeRuntime
       -> ProofNodeManager
            -> ReplSessionManager -> EasyCrypt
            -> ProofStateCompilerService -> bounded ActionSurface
```

The orchestrator owns proof-search topology. `ProofNodeManager` owns the agent
turn. `ReplSessionManager` alone mutates EasyCrypt. The compiler is read-only,
and L1 constructs no compiler service. The agent receives the current minimal
goal envelope plus any admitted compiler action and submits exactly one intent
through `submit_proof_intent`.

Do not restore the removed rich workspace/panel, inspect/search/lookup topic
menus, text-derived semantic analysis, historical surface profiles, or direct
agent use of `session_cli.py`. Runtime-generated MCP metadata and the current
surface are the only authority for available intents.

## EasyCrypt environment

EasyCrypt is repository-locked to official release `r2026.06`, commit
`1c7e6d78eb1cfb44a4c98e00e1b5ef8b5bfd30c9`.

```bash
uv run python tools/bootstrap_easycrypt.py
uv run python tools/bootstrap_easycrypt.py --verify-only
```

Python runtime entry points select the verified managed environment
automatically. Only developer commands that invoke `easycrypt` directly need:

```bash
eval "$(uv run python tools/bootstrap_easycrypt.py --print-env)"
```

If an OS sandbox blocks `why3server`/`nice()`, rerun the bounded test with the
required permission. Do not add a parser, stdout, ambient-opam, or stale-file
fallback.

## Eval safety

When `[EVAL MODE ACTIVE]` is present or `EVAL_TARGET_LEMMA` is set:

- do not read target-specific prior traces, cached proofs, or hints;
- do not inspect sibling or stale `.ec_session_*` directories for tactics; and
- reading the isolated target source and sibling lemmas in that source is
  allowed.

## Current documentation

- `AGENTS.md` — canonical runtime and agent contract
- `docs/ARCHITECTURE.md` — compact architecture map
- `docs/design/proof_state_compiler_v2.md` — compiler design authority
- `docs/architecture/proof_terminal_outcome.md` — final-proof outcome contract
- `TESTING.md` — current deterministic and live experiment procedure

Historical reports and offline bundle readers retain old names as provenance.
They do not define a runnable profile, context topic, or compatibility path.
