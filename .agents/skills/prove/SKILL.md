---
name: prove
description: Prove one EasyCrypt lemma in place with a managed Codex proof node. Use when the user explicitly invokes $prove or selects Prove from the Codex skill menu.
---

# Prove an EasyCrypt lemma

Run the ordinary in-place proof workflow on the user's source file. Keep the
proof-state compiler profile fixed. Do not enable eval mode, copy the project,
or strip proofs. The launcher owns the proof-node backend: the Codex `$prove`
skill always uses Codex, while the Claude Code wrapper that reads this workflow
always uses Claude. Never offer a cross-backend override.

## Parse the invocation

Interpret the invocation text as one positional token:

- token 1: lemma name, required, for example `PIR_correct`.

Ask for the lemma name if token 1 is missing. Reject extra positional tokens
instead of interpreting them as a backend or model. Use the fixed runtime profile
`proof_state_compiler`; do not offer control, audit, L-level, or retired run
mode choices through this skill.

## Run the managed workflow

1. Verify the repository-managed EasyCrypt toolchain:

   ```bash
   uv run python tools/bootstrap_easycrypt.py --verify-only
   ```

   Stop and report the verification error if this command fails. Do not fall
   back to an ambient EasyCrypt or opam installation.

2. Locate the target declaration when its file is not already unambiguous.
   Search the designated user workspace first:

   ```bash
   rg -l "(lemma|equiv|hoare)[[:space:]]+<LEMMA>" projects \
     -g '*.ec' -g '*.eca'
   ```

   Replace `<LEMMA>` with the requested lemma name. If there is no match, search
   the repository's checked-in examples:

   ```bash
   rg -l "(lemma|equiv|hoare)[[:space:]]+<LEMMA>" eval/examples \
     -g '*.ec' -g '*.eca'
   ```

   Do not broaden the search to vendored EasyCrypt, generated artifacts, run
   bundles, or historical reports. Inspect plausible matches before choosing.
   If multiple distinct declarations remain ambiguous, ask the user which
   target they intend.

   The checked-in examples contain complete reference proofs, so a run on one
   of them only reports that the lemma is already verified. Before launching,
   tell the user so, and point out that the demo suite
   `eval_suite/suites/demo_pir.json` (see the README) proves a proof-stripped
   copy of `PIR_correct` without changing their files.

3. Tell the user which file and lemma were resolved. The proof workflow may
   write a verified proof back into that target file; invoking `$prove` or
   `/prove` authorizes that scoped write. Do not edit the proof manually to
   help the agent.

4. Launch the managed orchestrator directly on the original source. For the
   Codex `$prove` launcher use:

   ```bash
   uv run python -m workflow.orchestrator \
     --file <FILE> \
     --lemma <LEMMA> \
     --include-dir easycrypt-src/theories \
     --max-iterations 1 \
     --prover-timeout-minutes 30 \
     --surface-profile proof_state_compiler \
     --agent-backend codex \
     --prover-model gpt-6-astra \
     --prover-effort high \
     --tree-initial-provers 1 \
     --tree-max-concurrent 1 \
     --output-dir artifacts/prove
   ```

   For the Claude Code `/prove` wrapper, use the same command with
   `--agent-backend claude` and omit `--prover-model`; Shannon then uses its
   Claude default, `claude-opus-4-8`. Do not add `--eval-mode`. Do not
   accept a backend or model override from the invocation text. A user who
   wants another model runs the command above themselves with a different
   `--prover-model`. A live proof can take tens of minutes; keep the user
   informed while it runs.

5. Report the canonical `ProverResult`, the target file, and the printed run
   directory. Count the proof as successful only when the terminal result is
   `verified`, which requires that the committed proof contains no `admit` or
   `admitted`, that the file has no weakening `pragma Proofs`, and that fresh
   offline EasyCrypt verification passed. Clearly distinguish an already-verified
   target, timeout, infrastructure failure, unverified output, and verified
   proof success.

This launcher is the user-facing proof tool, not a research evaluation. The
separate `eval_suite` workflow owns proof stripping, source isolation,
filesystem confinement, matched experiment arms, and benchmark metrics. Never
silently switch `$prove` or `/prove` into that evaluation workflow.
