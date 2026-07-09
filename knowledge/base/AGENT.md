# How to Use the Knowledge Base

This document tells you (the proof agent) how to use the knowledge base to write EasyCrypt proofs.

## Files

- **`agent/proof_guide.json`** — Strategies, EC syntax tips, and proof patterns. Contains:
  - `strategies`: proof roadmaps (IND-CPA, CCA, correctness, hiding, binding, sigma protocol, ...)
  - `ec_syntax`: EasyCrypt tactic syntax tips with common errors and fixes
  - `patterns`: structural proof patterns with generic role descriptions and reasoning hints
  - `closer_idioms`: small closing-pattern descriptions for residual goals
- **`agent/ec_tactics.json`** — **Execution-level reference.** Indexed by (goal_type, tactic). Contains:
  - `syntax`: canonical tactic form
  - `errors{}`: error patterns tagged as "execution" (wrong form → retry) or "strategy" (wrong tactic → switch)
  - `when_to_abandon`: conditions indicating this tactic is wrong for the goal
  - `smt_hints[]`: lemma names useful with smt() for this tactic's subgoals
  - Used by manager `goal_info` and `diagnose` context requests
- **`agent/decision_tree.md`** — **Proof planning guide**. Read this BEFORE starting a proof. Navigation tree for: oracle handling (sim vs apply vs inline), sampling coupling (identity vs bijection vs interleaved), postcondition closing (algebra vs bijection mapping vs boolean). Pitfalls (P1-P14) and recipes (R1-R10).
- **`search_guide.py`** — **Query tool** for proof_guide.json. Use instead of reading the JSON directly:
  ```bash
  python3 knowledge/base/search_guide.py "keyword"           # search by keyword
  python3 knowledge/base/search_guide.py --id pattern_id     # get specific entry
  python3 knowledge/base/search_guide.py --section ec_syntax "rnd"  # search section
  python3 knowledge/base/search_guide.py --list              # list all entries
  ```

## Workflow

### At the start of a proof

1. Read `agent/decision_tree.md` — follow the decision tree to plan your proof architecture.
2. Search the proof guide for matching strategies and patterns:
   ```bash
   # List all entries (quick index)
   python3 knowledge/base/search_guide.py --list
   # Search by keywords
   python3 knowledge/base/search_guide.py "byequiv sim equivalence"
   # Get a specific entry
   python3 knowledge/base/search_guide.py --id equiv_sim_structural
   # Search only ec_syntax tips
   python3 knowledge/base/search_guide.py --section ec_syntax "rnd swap"
   ```
   Do NOT read `agent/proof_guide.json` directly — it is too large. Use `search_guide.py`.
3. In managed prover runs, do not start an EasyCrypt session yourself. The
   manager has already initialized the session and handed you a
   `ProverWorkspaceView`.

### At each proof step

1. **Read your current goal state** from `ProverWorkspaceView.current_goal.lines`.
2. **Match to a pattern** — search for keywords from your goal:
   ```bash
   python3 knowledge/base/search_guide.py "loop invariant phoare"
   ```
   Find the pattern whose `structural_description` and `indicators` best match your goal.
3. **Look at the pattern's guidance**:
   - Use `variants` only to choose the structural case that matches the live goal.
   - Use `typical_tactics` as tactic categories, not as a stored script.
   - `reasoning_hints` / `smt_hints`: why it works and what lemma hints to use.
   - `common_failure` / `fallback`: what error to expect and how to recover.
4. **Instantiate from the live goal**: use slots and role descriptions to map the generic template onto your current variables and program positions. Do not look for stored per-lemma proof scripts.
5. **For syntax questions**: `python3 knowledge/base/search_guide.py --section ec_syntax "rnd bijection"`

### Pattern matching: how to think about it

After `proc.`, your goal shows the pRHL structure at the module/call
level. **Do NOT reflexively `inline *` next** — that drops you to
procedure-level and destroys the call sites that oracle-equiv pivots
(e.g. `call poly_mac1.`) match against. First describe the goal
at call-level:

- "Two games: both sample a secret, compute a public key, call the
  adversary, sample randomness, compute a ciphertext. Left has
  uniform masking on the ciphertext, right doesn't." → pattern:
  `equiv_sampling_swap_bijection`.
- "Single game: samples, calls, then a final uniform coin flip.
  Return guess = coin." → pattern: `phoare_coinflip_half`.
- "Loop that samples a bit each iteration, updates state
  conditionally." → pattern: `equiv_coupling_loop` or
  `phoare_loop_invariant`.

Match by **program roles** (what each statement does), not by
variable names.

**When to `inline` (choose the narrowest option that works):**
1. First: is `sim.` / `sim />.` sufficient? (structurally identical
   programs, possibly with renamed state.)
2. Next: is `call (_: <inv>).` with the invariant from manager
   `inspect_context` topic `inv_from_lemma` sufficient? (the sibling
   equiv's statement IS your invariant.)
3. Only when 1 and 2 don't apply: `inline <Specific.Proc>.` —
   targeted; exposes ONE procedure, leaves others as call sites.
4. Last resort: `inline *.`. This is a one-way drop from
   module-level to procedure-level. Once done, `call`, `sim`,
   and `conseq` on that call structure are all unreachable
   without undoing to an earlier frontier. Use only when the two programs have no
   matching call sites to preserve.

### Instantiating Generic Templates

When you find a matching pattern, the KB gives roles and placeholders, not a
stored example proof. Read the live goal to fill those roles:
- Determine program positions from the current pRHL/phoare view.
- Derive bijections from the current masking expression.
- Choose smt hints from the current theories and `ec_tactics.json`.

Concrete lemma proof scripts are intentionally not stored in the KB.

## Generic Guidance Notation

The KB uses role placeholders and tactic categories. It does not store
literal proof scripts to paste into a lemma. Treat all guidance as a prompt
to inspect the current goal and derive the concrete tactic yourself.

### Placeholders

- `<pos>`, `<offset>`, `<side>` — read the goal state, count statements to determine these
- `guess_var` — the adversary's guess variable. Read the goal to find it.
- `loop_bound`, `loop_counter` — read the while loop in the goal.

**Always read the goal state. Never guess position numbers.**

> **Manager context**: use `inspect_context` for `goal_info`, `align`,
> `diagnose`, `subgoal_gap`, `lemma_hints`, `inv_from_lemma`, and
> `bridge_probe`; use `lookup_symbol` for exact declarations.

## Verification and why3 Failures

When you verify your proof by running `easycrypt` on the full `.ec` file, some files contain
unrelated lemmas that use `smt()`. These lemmas require `why3server`,
which is unavailable in the sandbox (the OS blocks the `nice()` syscall). This causes the
full-file check to fail even when YOUR proof is correct.

**This is NOT a problem with your proof.** The workflow orchestrator uses extracted-lemma
verification: it isolates the target lemma into a standalone file (replacing other lemmas'
proofs with `admit`) and verifies only that. Your proof will be accepted even if sibling
lemmas in the same file depend on why3.

**Rule**: You do NOT need to avoid `smt()` in your own proof to make verification pass
(though `smt()` will also fail at runtime due to the sandbox — prefer manual tactics
like `case`, `apply Constructor`, `exact`, and `rewrite` + `ring`/`algebra`).

**If you see a why3 failure** while running `easycrypt` interactively:
- Check which lemma/line is failing — if it is NOT your target lemma, ignore it.
- If it IS your target lemma, your proof has an `smt()` step that needs to be replaced
  with manual tactics.
