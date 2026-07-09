# Eval: EasyCrypt Proof Tasks

The eval measures real EasyCrypt proof construction ability. Do not retrieve
cached target proofs.

Allowed context:

- files inside this project directory
- the target `.ec` file and sibling lemmas in that file
- EasyCrypt theories under `easycrypt-src/theories/`
- tactic examples under `easycrypt-src/tests/`
- generic KB guidance via `knowledge/base/search_guide.py` and
  `knowledge/base/agent/*`

Forbidden context:

- public internet or GitHub repositories
- `knowledge/session_trace/processed/`
- proof-bank or replay artifacts containing concrete tactic sequences
- target-lemma-name searches in knowledge stores when eval mode is active
- invented lemmas or axioms; use only declarations visible in source or
  manager-provided context

## Managed Prover Interaction

In workflow eval, the prover-agent protocol is generated at runtime from the
current surface profile, MCP tool schema, and manager workspace view. Do not
maintain a static intent or topic menu in this file.

The agent does not start or manage EasyCrypt sessions. It reads the latest
manager-provided `ProverWorkspaceView` and submits one proof-level JSON intent
through the manager-owned transport. Runtime-generated MCP metadata is the
authoritative source for allowed intents, context topics, and payload shapes.

## Human/Backend Debugging

`core/easycrypt/session_cli.py` still exists as a backend/human-debug tool, but
it is not the agent-facing protocol during managed eval runs.
