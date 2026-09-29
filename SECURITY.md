# Security policy

## Reporting a vulnerability

Please report security problems privately by email to
**shannonprover@gmail.com**, not in a public issue. Include a description of
the problem, the steps to reproduce it, and the version (public commit) you
used. We will acknowledge your report and keep you informed while we work on a
fix.

## What to keep in mind when running Shannon Prover

Shannon Prover launches third-party coding-agent command-line tools (OpenAI
Codex by default, Claude Code when selected) on your machine. These tools run
with access to the repository checkout, and their own configuration and
sandbox settings govern what else they can reach.

- Run Shannon Prover in a dedicated checkout, or in a virtual machine or
  container, rather than in a directory that holds unrelated private files.
- Keep credentials out of the repository. Agent tools authenticate through
  their own login mechanisms; do not place API keys in project files.
- Treat a finished proof as you would any generated code: EasyCrypt checks
  the statements in the submitted development, so also review that the
  theorem and assumptions are the ones you intended (see
  "What counts as a proof?" in the [README](README.md)).
- Controlled benchmark evaluation uses additional isolation, which currently
  requires Linux and `bubblewrap`; see the [benchmark guide](eval_suite/README.md).
