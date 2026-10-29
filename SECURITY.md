# Security policy

## Reporting a vulnerability

Please report security problems privately by email to
**shannonprover@gmail.com**, not in a public issue. Include a description of
the problem, the steps to reproduce it, and the version (public commit) you
used. We will acknowledge your report and keep you informed while we work on a
fix.

## What the agents can do on your machine

Shannon Prover launches third-party coding-agent command-line tools (OpenAI
Codex by default, Claude Code when selected) on your machine. It starts them
with its own settings and ignores your own Codex configuration and rules
files, so your usual sandbox and approval settings do not apply. It never
asks you to approve an agent action.

| Agent | Codex | Claude Code |
|---|---|---|
| Single-lemma prover (`$prove`, `/prove`, the demo suite) | Codex read-only sandbox | All permission prompts skipped. Its shell and file tools run with your user account and network access; only a short list of proof-corrupting operations, such as `rm` and edits to the proof source, is blocked |
| Project-level overall agent (`python -m workflow.interleaved`) | No sandbox (`danger-full-access`) | All permission prompts skipped (`bypassPermissions`) |
| Project-level auxiliary-lemma agents | Codex read-only sandbox, or `bubblewrap` confinement on Linux when installed | No built-in tools; it acts only through Shannon's proof tool |

The project-level overall agent runs for up to the configured time limit
(twelve hours in the example) with your user account's access to files,
credentials, network and Git. It needs a shell to start auxiliary-lemma jobs,
and Shannon does not confine it. No operating-system sandbox applies beyond
those named in this table.

- Run Shannon Prover in a virtual machine, container or separate user account
  that holds no unrelated private files or credentials, especially for
  project-level runs or when the EasyCrypt sources come from someone else.
- Keep credentials out of the repository. Agent tools authenticate through
  their own login mechanisms; do not place API keys in project files.
- Treat a finished proof as you would any generated code: EasyCrypt checks
  the statements in the submitted development, so also review that the
  theorem and assumptions are the ones you intended (see
  "What counts as a proof?" in the [README](README.md)).
- Controlled benchmark evaluation uses additional isolation, which currently
  requires Linux and `bubblewrap`; see the [benchmark guide](eval_suite/README.md).
