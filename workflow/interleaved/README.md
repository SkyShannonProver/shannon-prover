# Shannon Prover: project-level proving guide

Shannon Prover works on the construction of an entire EasyCrypt proof:
it proposes auxiliary lemmas, searches for their proofs, and revises the
decomposition as it learns which steps can be established. You provide the
security model and final theorem. See the [overview](../../README.md) for the
distinction between Phases I, II, and III.

## Prepare your project

Run commands from the repository root after completing the
[installation](../../README.md#install). Use a separate Git checkout for a
proof attempt if you want to keep other work independent: the overall proof
agent edits your target file directly.

Keep the target and all project-owned `.ec` and `.eca` dependencies together
under `projects/my-proof/`. The target must already load in EasyCrypt and
contain the final lemma with a proof block. An unfinished block may use:

```easycrypt
proof.
  admit.
qed.
```

You supply the definitions, assumptions, and target statement. You can also
supply helpful lemmas or a partial argument, but a decomposition is not
required. During development, unfinished proofs are allowed; the final check
rejects any remaining `admit.` in the target.

Save the following as `projects/my-proof/interleaved_project.json`, changing
`Target.ec` and `TargetSecurity` to your file and final lemma:

```json
{
  "schema_version": 1,
  "target_file": "projects/my-proof/Target.ec",
  "final_lemma": "TargetSecurity",
  "include_dirs": ["easycrypt-src/theories", "projects/my-proof"],
  "artifact_root": "artifacts/my-proof-interleaved",
  "max_parallel": 2,
  "max_inner_minutes": 120,
  "outer_timeout_seconds": 43200
}
```

All paths in this file are relative to the repository root. The results go
under `artifact_root`; use the ignored `artifacts/` directory so generated
files do not prevent the next run from starting. Keep local dependencies in
the target directory: delegated proof attempts copy that directory and the
EasyCrypt libraries.

Commit your project and configuration before running. Both preflight and live
runs require a clean Git working tree, including no unignored untracked files.

## Choose the agents and limits

The command-line terms **outer** and **inner** name two roles:

| Role | Responsibility | Current default |
|---|---|---|
| `outer` | Construct the overall argument, choose auxiliary lemmas, and assemble the final proof. | Claude Code, `claude-opus-5`, high effort |
| `inner` | Work on an auxiliary lemma selected by the overall proof agent. | OpenAI Codex, `gpt-5.6-sol`, high effort |

Both roles support `claude` or `codex`. For example,
`--outer-provider codex --inner-provider codex` uses Codex for both.
The exact models and provider limits are set in
[`agent_profiles.json`](agent_profiles.json); commit any changes before a run.
You need access to the selected models through the installed CLIs.

The runner requires stored OAuth authentication: a Claude login for Claude
Code and a ChatGPT login for Codex. It removes injected API credentials when
launching the selected agents. Preflight checks the installed CLIs, login
method, and required capabilities before proof generation begins.

The example configuration permits two simultaneous auxiliary-lemma attempts,
with at most 120 minutes per attempt and a 43,200-second (12-hour) overall
task. These limits do not cap total spending or the total number of attempts.
The checked-in Claude overall-agent profile additionally sets 8,000 turns
and a USD 500 budget; Codex has no corresponding runner-enforced monetary cap.

Set `outer_timeout_seconds` to change the project's overall time allowance.
The optional CLI flag `--timeout-seconds` changes the external stop timer
only; it does not rewrite the task allowance recorded for the agent. Keep
these aligned for ordinary use.

## Check the setup, then run

First perform the checks without starting a proof-generating model:

```bash
uv run python -m workflow.interleaved \
  --project projects/my-proof/interleaved_project.json \
  --preflight-only
```

Preflight checks the project with EasyCrypt, prepares the source files needed
for delegated lemmas, and checks the selected agent installations. It still
uses the local toolchain and provider CLIs. If it fails, read the terminal
error and the files under the printed or newly created results directory;
fix the setup before starting a live run.

To start proof construction, remove `--preflight-only`:

```bash
uv run python -m workflow.interleaved \
  --project projects/my-proof/interleaved_project.json
```

For Codex in both roles, add both provider flags to **both** commands:

```bash
uv run python -m workflow.interleaved \
  --project projects/my-proof/interleaved_project.json \
  --outer-provider codex --inner-provider codex \
  --preflight-only
```

The overall agent may write proofs directly or delegate auxiliary lemmas.
The final theorem is assembled by the overall agent. It may use partial
progress to revise its approach, but partial progress is not proof success.

## Read the result

The command prints a results directory below your configured
`artifact_root`. It contains:

| File | What it tells you |
|---|---|
| `manifest.json` | Selected agents and models, time limits, run status, and whether final verification passed. |
| `final_verification.json` | The final EasyCrypt check and any errors. It is produced after a live proof attempt. |
| `partial_candidate.ec` | A saved copy of the target when the attempt did not pass final verification. |

A completed interleaved proof has `status: "proved"` and
`final_verification_passed: true` in the manifest. A preflight result only
establishes that the setup passed; it does not prove the theorem. An individual
auxiliary lemma may be verified while the overall run remains incomplete.

The complete candidate is in the configured target file. Review its diff:
the overall agent edits this file during the attempt, including when the
attempt fails. This differs from the single-lemma `$prove` command, which
writes back a generated proof only after verification.

### Preserve the intended security problem

The built-in verifier runs the pinned EasyCrypt on the complete target,
requires the named final lemma to exist, and rejects `admit.` in the target
at final verification. It does **not** enforce byte-for-byte preservation of
your original theorem, definitions, assumptions, or dependency files.

For a fixed security claim, review those changes and add project-specific
restrictions where needed. The optional `prompt_file` supplies your proof
instructions; the optional `verifier` supplies an executable Python checker.
Both are repository-relative paths. The runner invokes the checker with
`--preflight`, `--check`, or `--final`, plus `--output PATH`; it must
return a nonzero exit code on failure. A replacement verifier must retain
the EasyCrypt and unfinished-proof checks as well as your additional
restrictions. A prompt instruction alone is not a verification gate.

The [ChaChaPoly example](../../experiments/interleaved_shannon/README.md)
demonstrates a stricter checker that preserves a fixed problem and its
supporting files.

## Continue an incomplete attempt

Review and commit a loadable checkpoint so the checkout is clean. Keep the
previous results directory in place. A continuation can then load its saved
candidate:

```bash
uv run python -m workflow.interleaved \
  --project projects/my-proof/interleaved_project.json \
  --continuation-of artifacts/my-proof-interleaved/official_TIMESTAMP \
  --continuation-candidate \
    artifacts/my-proof-interleaved/official_TIMESTAMP/partial_candidate.ec
```

Replace `official_TIMESTAMP` with the actual directory name. The new run
records its connection to the prior attempt and inherits its provider choices.
Changing a provider requires `--allow-provider-change` and is recorded.
Compatible saved lemma progress can be made available to the agent; a
continuation is not a guarantee that every interrupted step can be resumed.

## Scope

This interface supports projects with a final EasyCrypt lemma and local
dependencies. It does not turn an informal security claim into a formal
security model, guarantee a successful decomposition, or establish a runtime
advantage over another approach.

The [architecture notes](../../docs/architecture/interleaved_shannon.md)
describe delegation, proof checking, and saved progress for contributors.
The current proof browser displays individual lemma attempts; it does not
display a complete interleaved run.
