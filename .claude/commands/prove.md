---
description: Prove an EasyCrypt lemma with Shannon Prover (eval-mode; L4 by default)
argument-hint: <LemmaName> [surface_profile]
allowed-tools: Bash, Grep, Glob, Read
---

Run Shannon Prover on a single EasyCrypt lemma for the user.

Input: `$ARGUMENTS`
- token 1 = lemma name (required), e.g. `PIR_correct`.
- token 2 = surface profile (optional, default `l4_checked_action_surface`): one of
  `l1_goal_projection`, `l2_semantic_ir`, `l3_flow_navigation`,
  `l4_checked_action_surface`, `adaptive`.

Substitute `<LEMMA>` / `<PROFILE>` / `<suite>` / `<id>` below from the input as you go.

Steps:

1. Environment — EasyCrypt must run outside any OS sandbox so `why3server` can start
   (it needs the `nice()` syscall):

   ```bash
   eval "$(opam env --switch=easycrypt)" && mkdir -p tmp
   ```

2. Locate the lemma's source under `eval/examples/` if it is not obvious:

   ```bash
   grep -rln "lemma <LEMMA>\|equiv <LEMMA>\|hoare <LEMMA>" eval/examples --include=*.ec
   ```

   A single self-contained file directly under `eval/examples/` needs no `copy_root`.
   A target inside a project subdir uses that subdir as its `copy_root`.

3. Pick the suite. For `PIR_correct`, use the worked demo `eval_suite/suites/demo_pir.json`.
   Otherwise copy it to `eval_suite/suites/local_<LEMMA>.json` and edit `targets[0]` only
   (`id`, `file`, `lemma`, plus `copy_root` for multi-file targets). Keep
   `eval_mode`, `strip_proofs`, `source_isolation` = `true` and
   `max_iterations` = 1.

4. Dry-run first and confirm the expanded command points at an isolated source under
   `artifacts/eval_suite/.../source/...` (never the live checkout):

   ```bash
   uv run python -m eval_suite.run --suite eval_suite/suites/<suite>.json --profiles <PROFILE> --dry-run
   ```

5. Run it:

   ```bash
   uv run python -m eval_suite.run --suite eval_suite/suites/<suite>.json --profiles <PROFILE> 2>&1 | tee tmp/<LEMMA>_<PROFILE>.log
   ```

   On a Claude subscription with no provider API key, prefix the run with
   `env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u OPENROUTER_API_KEY -u DEEPSEEK_API_KEY`
   so the Claude CLI uses the logged-in subscription.

6. Report the verdict:
   - `artifacts/eval_suite/<suite>/<PROFILE>/<id>/r01/eval_metrics.md` — solved? turns? wall time?
   - the run bundle `agent_view_runs/<LEMMA>/<TS>__<commit>/timeline_report.md` — each
     turn's agent view -> intent -> manager result, plus the reconstructed committed proof.
   - It is a real success only if the proof contains **no** `admit.` Check for it.

Do not hand-edit the checkout to "help" the proof — eval-mode isolation copies and
scrubs the target lemma in a per-run container on purpose.
