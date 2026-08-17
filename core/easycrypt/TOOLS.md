# EasyCrypt Backend Interface

`session_cli.py` is a manager/backend and human-debug transport. It is not an
agent-facing tool. The proof agent uses only the manager-owned
`submit_proof_intent` MCP method.

## Current command surface

```text
python3 core/easycrypt/session_cli.py -d SESSION \
  (-start |
   -tactic-exec commit|commit_chain|undo |
   -try |
   -managed-goal-view |
   -episode-view |
   -compiler-input-v2 |
   -compiler-resource-load-v2 |
   -native-semantic-batch-json |
   -native-state-projection-json |
   -verify LEMMA)
```

Run `python3 core/easycrypt/session_cli.py --help` for request fields. New
workflow code must not depend on retired `-next/-prev/-chain`, rich
`-agent-view`, goal analysis, inspect/search/lookup, or tactic-form commands.

## Mutation

The canonical manager mutation entry is:

```bash
python3 core/easycrypt/session_cli.py -d SESSION \
  -tactic-exec commit -c 'TAC.'

python3 core/easycrypt/session_cli.py -d SESSION \
  -tactic-exec commit_chain --keep-on-fail -c 'T1. T2.'

python3 core/easycrypt/session_cli.py -d SESSION \
  -tactic-exec undo
```

`ReplSessionManager` is the only production caller authorized to start, mutate,
undo, restart, or replay a managed session. Direct commands are for bounded
developer diagnosis.

## Read-only current artifacts

| Command | Result |
|---|---|
| `-managed-goal-view` | Exact current goal/status/identity envelope |
| `-episode-view` | Event-bound current episode timeline |
| `-compiler-input-v2` | State-only compiler input joined to current manager/state identity |
| `-compiler-resource-load-v2` | Bounded declaration resources bound to one prior compiler-input occurrence and exact `StateRef` |
| `-native-semantic-batch-json` | One bounded, ordered batch of tagged EasyCrypt-native semantic descriptors |
| `-native-state-projection-json` | EasyCrypt-native typed current-state projection |
| `-try` | Exact tactic preflight in the unchanged current state |
| `-verify LEMMA` | Final source/lemma verification |

Every semantic result is a unique current-call produced artifact. Stdout is
only a human display. It cannot replace, repair, or override the event-bound
artifact.

## Exact tactic preflight

`-try` emits `tactic.preflight.produced`. The result records the exact tactic,
explicit outcome, progress/residual-goal evidence, session and goal identity,
and artifact hash. It is read-only. The compiler certification gateway accepts
an action only from this exact shape; it does not consume a generic guidance or
tool-view envelope.

## Native compiler adapters

EasyCrypt is the semantic authority for:

- parsing and typed declarations;
- name, theorem, module, and procedure resolution;
- goal/local/program typed state;
- proof-term argument kinds;
- formula/type/module/proof matching;
- implicit arguments, holes, and concretization; and
- tactic acceptance and residual proof obligations.

The native wrappers in this directory schedule bounded requests and bind
results to the exact build/session/state. Python compiler code may form lexical
candidate sketches, but it must not reproduce these semantics or fall back to
source-text inference when a native request fails.

`compiler_namespace_adapter.py` is a bounded declaration-namespace adapter. It
uses EasyCrypt `print theory` / exact `print` results only to enumerate and load
candidate declarations. It does not guess clone prefixes, search sibling files,
or provide typed application semantics.

## Event authority

A valid current-call reader checks:

1. matching `tool.called` and `tool.result` boundaries;
2. exactly one expected produced event inside that call;
3. action/session/request/state identity;
4. event order and process exit;
5. artifact confinement and SHA-256; and
6. payload schema and explicit outcome.

Failure is closed: no older artifact, raw output, or filesystem heuristic is a
semantic fallback.

## Environment

EasyCrypt is provided by the repository-managed `r2026.06` toolchain selected
and verified by `ec_env.py`. Bootstrap once and verify before backend work:

```bash
uv run python tools/bootstrap_easycrypt.py
uv run python tools/bootstrap_easycrypt.py --verify-only
```

Keep the `uv` launcher outside the project `.venv`. In particular,
`.venv/bin/uv` must not be used to recreate the same environment. After an
environment is synchronized, use `.venv/bin/python
tools/bootstrap_easycrypt.py --verify-only` when no stable external `uv` is
available.

Python entry points select it automatically. For developer-only direct
EasyCrypt commands, export the verified environment with:

```bash
eval "$(uv run python tools/bootstrap_easycrypt.py --print-env)"
```

`why3server` may fail under an OS sandbox that blocks `nice()`. Rerun the
bounded backend test with the required permission. Do not change compiler
semantics to accommodate a sandbox failure.

## Developer rules

- Do not expose these commands in the agent prompt or MCP schema.
- Do not read sibling/stale `.ec_session_*` directories for proof content.
- Do not add a text parser as fallback for a native semantic result.
- Do not restore a global inspect topic registry.
- Add a schema/event/no-mutation test for every new read-only artifact.
- Add a real EasyCrypt sentinel for every new native semantic claim.
