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
   the repository's checked-in examples so bundled demos such as `PIR_correct`
   remain runnable:

   ```bash
   rg -l "(lemma|equiv|hoare)[[:space:]]+<LEMMA>" eval/examples \
     -g '*.ec' -g '*.eca'
   ```

   Do not broaden the search to vendored EasyCrypt, generated artifacts, run
   bundles, or historical reports. Inspect plausible matches before choosing.
   If multiple distinct declarations remain ambiguous, ask the user which
   target they intend.

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
     --prover-model gpt-5.6-sol \
     --prover-effort high \
     --tree-initial-provers 1 \
     --tree-max-concurrent 1 \
     --output-dir artifacts/prove
   ```

   For the Claude Code `/prove` wrapper, use the same command with
   `--agent-backend claude` and omit the Codex `--prover-model` value so the
   Claude runtime selects its own default. Do not add `--eval-mode`. Do not
   accept a backend override from the invocation text. A live proof can take
   tens of minutes; keep the user informed while it runs.

5. Report the canonical `ProverResult`, the target file, and the printed run
   directory. Count the proof as successful only when the terminal result is
   `verified`, the committed proof contains no `admit.`, and fresh offline
   EasyCrypt verification passed. Clearly distinguish an already-verified
   target, timeout, infrastructure failure, unverified output, and verified
   proof success.

This launcher is the user-facing proof tool, not a research evaluation. The
separate `eval_suite` workflow owns proof stripping, source isolation,
filesystem confinement, matched experiment arms, and benchmark metrics. Never
silently switch `$prove` or `/prove` into that evaluation workflow.
