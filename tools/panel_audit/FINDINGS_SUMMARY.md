# Panel-Audit — Consolidated Findings (orchestrator re-audit)

Method: deterministic replay of **real recorded agent action scripts** (probe/
commit/inspect/lookup, extracted from `agent_view_runs/` bundles) through the
**current mcp-v0 code**, capturing per turn the **genuine raw EasyCrypt output**
(ground truth) vs the **current-code inline-read panel**. 5 runs / 67 turns,
spanning phoare (mee), equiv/pRHL (equiv_fwhile), pr/phoare (pr_G4), and pr
(pr_distinguish, at both L1 and L4). 7 specialist auditors + orchestrator
verification. No live LLM in the loop.

Harness: `tools/panel_audit/replay_audit.py` (+ `run_batch.sh`). Artifacts under
`artifacts/panel_audit/<run>/steps/turn_NNN/`. Per-dimension reports:
`findings/01..07_*.md`.

Legend: ✅ = orchestrator-verified against code+raw EC; ⚠️ = agent-reported,
code-located, not independently re-verified.

---

## TIER 1 — real bugs, high impact

### B1 ✅ "Already tried at this exact state" labels FAILED commits/probes as accepted/clean
- **Danger: a looping agent is told two failed tactics succeeded.**
- Evidence (`pr_G4_L4` turn_029, goal_hash `793830b9`): raw EC says
  `wp.` → `ok:false, status:"no_progress_reverted"` (`text-equal`); `seq 13 …`
  → `ok:false, status:"error", "[error] optional bound parameter not supported"`.
  Panel "Already tried" block prints **both** as `→ accepted`. (`equiv_fwhile_L4`
  turn_008: a `parse error` probe shown as neutral "probed (state unchanged)".)
- Root cause: `workflow/proof_node_runtime.py::_md_tried_here` (~L1669-1676) keys
  the verdict on `o.get("ok")` (the **ManagedTurn.ok**, which is `True` even on a
  DAEMON_REJECTED / no-progress-auto-reverted commit) and only consults the
  already-collected `error_summary` inside the never-taken `if not ok:` branch.
  Verified: timeline records `ok=True` with `error_summary=['text-equal']` /
  `['[error] optional bound parameter not supported']` for those very turns.
- Fix: treat a commit as **not accepted** when `error_summary` is present or the
  observation status is `no_progress*/error/*rejected`, regardless of `ok`.

### B2 ✅ Two-sided (pRHL) surgery tactics leak onto single-sided phoare/hoare goals
- Convergent: dim-04 (goal-class), dim-05 (L4 noise), dim-06 (candidates).
- Evidence (`mee` turn_002 phoare; `pr_G4_L4` turn_024/026/028 hoare cut with
  `pre = true`, single program): the "Need more?" inspect menu + candidate moves
  offer `sim`, "weaken to a smaller **relation** before `sim`", `rnd` "one side …
  sample coupling", `eager/lazy`, `swap` "across the two sides" — relational
  tactics that cannot type-check on a single program. The block is
  **byte-identical across 6 consecutive `pr_G4` commit turns** and is the dominant
  L4 commit-turn bloat (commit turns 1.55–2.51× the L1 line count).
- Root cause: `core/easycrypt/session_prover_workspace_view.py::_manager_context_handles`
  splices `*_prhl_surgery_tactic_handles()` (L1908) into every procedure goal
  family (L1758/1814/1864) keyed only on the `goal_family` string — **no
  single-sided gate**. The recent "single-sided hoare/phoare must not get the
  two-sided surgery panel" fix landed only on the FOCUS panel (`surface_profiles
  ._phase_of`), not on this handles/menu path. Confirmed correct on the genuine
  relational `equiv_fwhile_L4` run, so the strings are fine — the gate is missing.
- Fix: gate `_prhl_surgery_tactic_handles()` (and the relational candidate moves)
  on a two-sided-goal predicate, reusing the `_SINGLE_SIDED_GOAL_TYPES` check.

### B3 ✅ `frontier_call_sites/live_call_sites = 0` while `call_sites` is populated → Call-Frontier panel suppressed; sp-hint crosses the loop boundary
- Convergent: dim-03 (call frontier), dim-07 (consistency).
- Evidence (`mee` turns 02–15; `pr_G4_L4` turns 04–16/24–29; 29 turns): one view
  has `program_frontier.focus.frontier_call_sites:0, live_call_sites:0` while the
  same view's `program_frontier.call_sites` lists a real call (`pr_G4` t028:
  statement 13 `(m0,m1) <@ G4.A.choose(...)`) and `call_site_surface` /
  alignment rows describe live call frontiers + residuals. `call_site_surface
  .live_call_sites` and `focus.live_call_sites` share a name yet disagree (they
  AGREE =3 on the equiv run, so the divergence is a defect).
- Consequence: the L4 panel gates "Call Frontier" rendering on
  `frontier_call_sites>0` (commit 0e83b98e), so on every goal whose only calls
  are inside a loop/branch the agent gets **no call-frontier panel despite live
  calls**. Plus the "straight-line setup" region absorbs the first **in-loop**
  body statement (mee: `left_paths [..,"7.1"]`, 7.1 is inside the `while`), so
  `absorb_depth.left=7` and `sp_hint:"sp 7 0"` tell the agent to `sp` across the
  loop boundary.
- Root cause: `core/easycrypt/.../ec_program_ir.py::_mark_frontier` defines "the
  frontier" as the **last top-level statement**, so calls nested in loops/branches
  are never `is_frontier_call` → `frontier_call_sites=0`.

---

## TIER 2 — real, medium

- **B4 ⚠ (dim-03 CF-3)** Genuine two-sided equiv: the rendered Surgery panel
  prints right-only rows as `frontier: both sides at \`no matching left-side
  call…\``. `workflow/surface_profiles.py:646` checks only `right` for the
  placeholder and always prints `left`, so a **right-only** call/guard row is
  inverted to "both sides" and the right-program content is erased
  (`equiv_fwhile_L4` turn_001, the `if (k<>i)` guard + right-side call at 4.2.1.1).
- **B5 ✅ (dim-04 04-B, dim-05 F3)** Pr absolute-difference goal
  `|Pr[A]−Pr[B]| <= …` (`pr_distinguish` L4+L1) is labeled `probability/pr` and
  led with a `byphoare/byequiv` "Opener", but the real route is
  `ler_trans/ler_add/rewrite/smt` — which the **genuine L1 proof of the same
  lemma actually uses**. Root: `ec_goal_parser.classify_goal` fires on any `Pr[`.
- **B6 ⚠ (dim-06 F06-1)** Accepted-probe handle self-contradicts: same object
  says `why_relevant:"Daemon probe accepted this tactic …"` **and**
  `verified:"unverified_suggestion", derivation:"… not daemon-checked"` (`mee`
  t001/003/005/015). Verified provenance (`epistemic_status=daemon_probe_accepted`)
  is dropped between the recommendation producer and the thin handle, then
  re-stamped conservatively. (raw EC: `[TRY] accepted: True`.)
- **B7 ⚠ (dim-06 F06-2)** Abstract body-less op advertised as unfoldable:
  `unfoldable_goal_heads` lists `hmac_sha256` with `rewrite /hmac_sha256.`, but
  `FunctionalSpec.ec:382 op hmac_sha256: mK -> msg -> tag.` has no `=` body, so
  `rewrite /` can't delta-reduce it. `_UNFOLDABLE_DECL_HEAD_RE` matches the decl
  head without checking for a body.
- **B8 ✅ (dim-06 F06-3)** Fabricated lemma name: candidate move
  `rewrite perm3_perm3.` — `Perm6.ec:613` only has `perm3_perm3'` (primed, takes
  `&m sigma q`); `perm3_perm3` exists nowhere. Gated "route context, not to run
  as-is", so lower blast radius, but the name is fabricated.
- **B9 ⚠ (dim-03 CF-2)** `absorb_depth.note` claims "the body parser under-counted
  the asymmetric **(right-only) setup statements**" on **phoare goals that have no
  right side at all** (`mee` t002, `pr_G4` t004). Emitted unconditionally whenever
  the (B3-inflated) alignment count ≠ body-parser count.
- **B10 ✅ (dim-07 C3)** `proof_status.status:"error"` leaks onto a **read-only**
  turn (`pr_G4_L4` turn_029 `lookup_symbol`; L1 turns 4/5/10/11): the committed
  state is `open` with 8 goals and the rendered `## Status` line says "remaining
  8" with no error, but the JSON `status` is `"error"`. `status` tracks "did the
  last intent fail" instead of the committed proof state. Masked in markdown;
  recovers on the next successful commit.

---

## TIER 3 — cosmetic / nits
- Probe previews strip EC's blank separator lines while commit goals keep them
  (same goal renders 39 vs 34 lines) — no content lost (dim-01 F1).
- No-progress commit prints `**EasyCrypt error:** text-equal`, labeling an
  internal sentinel as an EC error one line under "there is no error to fix"
  (dim-02 F3).
- Probe no-op headline asymmetry (`## Current Goal (unchanged)` vs `🔍 Probe`)
  (dim-02 F2).
- Compact "(unchanged)" goal cuts to 8 inline lines on read-only turns (by
  design, flagged + recoverable) (dim-01 F2).

---

## POSITIVES — confirmed faithful (negative results matter)
- **Goal text is byte-faithful on all 67 turns** — including the 39-line
  two-column pRHL equiv goal, type annotations (`<:msg>`, `witness<:block>`), the
  `[NNN|check]>` prompt, and `pre/post/Context/Bound`. Truncation flags accurate;
  `(+N more)` counts correct; `(unchanged)` always true.
- **Tactic verdict/error fidelity is excellent.** The previously-recorded
  false-"rejected" probe family (`inline *.`, `inline …fi.`, `wp.` no-op) is
  **fixed** in current code and now matches raw EC. Real EC errors are surfaced
  **verbatim** with a "⚠️ Recover — last committed tactic was REJECTED" banner.
- **lookup_symbol passthrough is honest** — `[WHERE-MISS]` is never dressed up as
  a hit; `[WHERE-HIT]` bodies, `[AMBIGUOUS]` clone notes, and trust caveats
  (`PROOF STATUS: admit`, `SCOPE: exported_after_section`) are preserved verbatim.
- **inspect answers faithful** (goal_info, tactic_forms, align, diagnose's honest
  "No errors found").
- **State tracking faithful** — remaining-goal counts match EC exactly (no
  off-by-one/stale), goal_hash unchanged/changed tracking correct, "already tried"
  **scoping** correct (only same-hash moves; the only bug is the per-move
  verdict, B1).

## FIXES APPLIED (this session, verified by re-replay + 81 unit tests green)
- **B1 fixed** — `workflow/proof_node_runtime.py::_md_tried_here`: verdict now
  derives from EC's real result (`error_summary` presence + no-progress
  classification), not `ManagedTurn.ok`. Re-replay (`pr_G4` t029): `wp.` →
  "NO-OP (accepted by EC but no progress; auto-reverted)", `seq 13…` → "REJECTED:
  [error] optional bound parameter not supported", and the rejected `rnd.` probe
  → "REJECTED: invalid last instruction" (C2 also fixed).
- **B2 fixed** — `core/easycrypt/session_prover_workspace_view.py`: threaded
  `goal_type` into `_workspace_want_more_context` → `_manager_context_handles` →
  `_prhl_surgery_tactic_handles(two_sided)`. On single-sided (`hoare/phoare/
  bdhoare`) goals the two-sided-only `eager` handle is dropped; wp/swap/rcondt/
  rcondf/conseq/rnd (all single-sided-valid) are KEPT; two-sided equiv keeps the
  full toolbox incl. `eager`. Verified on mee (phoare) and equiv (pRHL).
- **B9 fixed** — `core/easycrypt/analysis/ec_procedure_actions.py`: the
  absorb_depth note no longer hardcodes "(right-only)"; it states the two counts
  neutrally and only says "right-only" on a genuine right side.

## T2 FIXES APPLIED (verified by re-replay + 216 unit tests green)
- **B4 fixed** — `workflow/surface_profiles.py`: the frontier-row renderer now
  detects the placeholder side symmetrically. A right-only row no longer renders
  as "both sides at `no matching left-side call…`" (which erased the right
  program); it reads "right side only" with the real right content. Verified on
  `equiv_fwhile_L4`: 9 "right side only" rows recovered.
- **B5 fixed** — `workflow/surface_profiles.py::_render_opener_focus`: for an
  abs-diff / multi-term `Pr` goal the opener now leads with the order/transitivity
  step (`apply (ler_trans …)` / `|·|` norm / `ler_add`) that must precede any
  byequiv/byphoare, instead of only offering the single-Pr reduction binary.
- **B6 fixed** — `core/easycrypt/session_workspace_view_manager.py` +
  `session_prover_workspace_view.py`: the structured provenance (`confidence`,
  `epistemic_status`, `source`) is now carried from the option through the thin
  `selected_handles` twin, so the provenance stamper classifies a
  daemon-probe-accepted handle as a `read_only_probe_suggestion` ("surfaced from
  try") instead of contradicting "Daemon probe accepted…" with "not
  daemon-checked / unverified_suggestion".
- **B7 fixed** — `core/easycrypt/analysis/ec_name_resolution.py`: a new
  `_declaration_has_body` gate drops body-less abstract ops (e.g. `op hmac_sha256
  : … .`) from `unfoldable_goal_heads` (no more misleading `rewrite /hmac_sha256.`);
  ops WITH a body (`mee_dec`, `unpad`) are kept. Conservative: ambiguous parse ⇒
  keep. Unit-tested on 7 declaration shapes.
- **B8 fixed** — `core/easycrypt/session_goal_context.py` (+ the `\b`-after-prime
  name regexes in `ec_lemma_index.py` / `ec_name_resolution.py`): the pr-bridge
  lemma scanner captured the name with `(\w+)\b`, and `\w`/`\b` drop the trailing
  EasyCrypt prime — so `perm3_perm3'` surfaced as the non-existent `perm3_perm3`.
  The name class now includes `'` with a `(?![A-Za-z0-9_'])` boundary. Verified:
  candidate is now `rewrite perm3_perm3'.`.
- **B10 fixed** — `core/easycrypt/session_prover_workspace_view.py::_workspace_proof_status`:
  an `error`/`no_progress` action outcome no longer leaks into the COMMITTED
  proof-state panel while a goal is still open; `proof_status.status` reports
  `open` (the action failure is still surfaced via last_result / recovery banner /
  diagnose handle). Verified on `pr_G4` t029: `status=open, remaining=8`.

## B3 — re-examined; one real bug fixed (option A), two reported symptoms are by-design
After tracing the frontier model end to end, the B3 cluster splits into:
- **NOT bugs (intended):** `frontier_call_sites = 0` is correct —
  `ec_program_ir.py::_mark_frontier` defines the frontier as the LAST top-level
  statement, so calls nested in loops/branches are deliberately not frontier
  calls. The Call-Frontier panel suppression is the *fix* introduced by commit
  `0e83b98e` (an in-loop call isn't `call`-able yet; it routes to the surgery
  toolbox). The auditor's "Call Frontier wrongly suppressed" was a misread.
- **Naming, not a fidelity bug:** `program_frontier.focus.live_call_sites` (=0,
  "frontier-reachable live calls") and `call_site_surface.live_call_sites` (=2,
  "call sites present in the goal") are two metrics sharing a name. Both correct.
- **B3-A FIXED AT THE SOURCE (real bug)** — root cause was that
  `ec_procedure_frontend.py::procedure_structured_regions` classified EVERY
  assignment — including in-loop/in-branch body statements like `7.1` — as a
  `straight_line_prefix` (setup) region, with no nesting filter, and the alignment
  partition swept them all into the setup prefix. Fixes:
  1. `procedure_structured_regions` now gates the two SETUP kinds
     (`straight_line_prefix`/`wrapper_or_init`) on top-level; a nested body
     statement is no longer a setup region (nested CALL/sample/control regions
     still surface, so the call-frontier rows survive).
  2. `procedure_straight_line_prefix` cap raised 4→16 so the second parser agrees.
  3. `_frontier_setup_counts` keeps a dotless-path guard as a defensive invariant.
  Result is correct at the SOURCE, not just the count: mee setup row is now
  "6 setup statement(s)" / paths `[1..6]`, residual `['8']` (was the incoherent
  `[7.3,7.4,7.5,8]`), absorb=6, the 6-vs-4 discrepancy note is GONE, hint `sp 6 0`;
  equiv left setup `['1']` (in-loop `2.1` dropped at source) → `sp 1 2`; pr_G4
  unchanged. Call-frontier rows preserved. Verified by re-replay + full test suite
  (1411 passed; the 2 failures are pre-existing & unrelated — IO-policy and
  prompt-embedding).

## Single most important fix
**B1** — `_md_tried_here` must derive the per-move verdict from EC's real status
(`error_summary` / observation status), not from `ManagedTurn.ok`. Today it tells
a stuck agent that EC-rejected and no-progress tactics were "accepted".

## Ergonomics audit (layout, not fidelity) — tools/panel_audit/ergonomics.py
Measured section line-budgets / proportion / answer-position across mee,
held-out-mac (a run from the private held-out MAC corpus), pr_G4 (60 turns).
Findings:
- probe panels: GOOD (goal/preview 79–91%, boilerplate 6–8%, goal-first).
- commit panels: a static ~28-line inspect menu = 26–35% of every commit,
  byte-identical turn to turn. (NOT yet fixed — bigger follow-up.)
- inspect/lookup panels: the REQUESTED answer was only 3–9% while the re-shown
  goal (30–50%) + legal anchor (22–25%) + "Manager result" echo (9–10%) dominated;
  on large goals the goal first appeared at line 8 (analysis above it).

FIXED (inspect/lookup ergonomics, `proof_node_runtime.py` retrieval branch):
answer-led, low-chrome. Order is now answer → (compact) goal → already-tried →
submit. Dropped the per-turn Legal Node Memory Anchor (recovery owned by the
system prompt — same precedent as the probe surface) and the 4-line "Manager
result" echo; the read-only disambiguation is preserved as a one-line note (so an
embedded accepted/rejected in a preview isn't misread as the current error).
Result: inspect/lookup panels ~35% shorter (mee 40→26 / 43→29; held-out-mac 47→33 /
50→36 lines), boilerplate ~28%→~7%, answer leads. Full suite 1411 passed (2
pre-existing unrelated failures).

NOT fixed (follow-ups): the commit-turn static inspect menu (~28 lines, identical
each commit); never render a focus panel above the goal on large goals.

## Commit-turn inspect-menu gating (data-driven; tools/panel_audit/inspect_usage.py)
Studied the real intent stream of ALL 72 recorded trees (1797 turns, no replay):
- retrieval (inspect+lookup) is 9% of turns; **after an accepted commit only 6%**
  lead to a retrieval (63% commit again, 24% probe).
- the menu's topic-set is **identical to the previous turn on ~78% of commits**.
- when agents DO inspect, the topics are real & phase-specific (tactic_forms 34,
  call_site_options 18, call_invariant_skeleton 17, diagnose 12, pr_bridge_routes
  12, call_subgoals 10).

So the 28-line menu on every commit was ~94% unused, yet load-bearing the ~6–9%
of the time it surfaces a phase-specific topic. Rule (proof_node_runtime.py): on a
commit turn the FULL verbose menu is shown only when it earns its place —
  (a) the topic-set changed vs the previous turn (new phase / first turn),
  (b) recovery: this commit was rejected / made no progress, or
  (c) stall: the last 3 turns had no accepted commit.
Otherwise it collapses to a ONE-LINE pointer that still names the phase's topics
(`_menu_topics_changed` / `_recent_stall` / `_md_reference_terse`). Verified on
pr_G4: 6/13 commits FULL (phase entries + the rejected seq-13 recovery), 7/13
terse, saving ~32 lines each. Full suite 1411 passed.

## Adversarial re-audit (6 agents over the session's diff) — regressions found & fixed
The 10 original fixes (B1/B3-root/B7/B6/B8/B10/B4) re-verified CLEAN (no regressions:
top-level setup gate drops only nested assigns never calls/loops/samples; prime regex
no over-capture; status normalization hides no real error; has_body drops no genuinely-
unfoldable op). But the two rendering redesigns introduced 5 issues, ALL now fixed:
- **E-BUG1 (high)** recovery trigger was DEAD — read `error_summary` at the top level of
  the live `turn.manager_actions`, but it is nested under `agent_observation`. A
  no-op/rejected commit rendered terse instead of full. Fixed via `_turn_action_errored`
  (checks both levels). Verified: pr_G4 t026 no-op → FULL.
- **D1 (high)** retrieval `## Requested:` heading was gated on inline `detail`, so
  focus-panel-answer topics (goal_info / call_site_options / pr_bridge_routes) rendered
  with NO acknowledgement the inspect was served. Fixed: heading ALWAYS emitted; the
  read-only note still attaches only when there is inline answer text.
- **R5 (med)** the B5 opener over-fired the `ler_trans` order-step on a bare `Pr[A]=Pr[B]`
  EQUALITY (and matched `<=` in premises like `0 <= sigma_ =>`). Fixed: gate on abs-diff
  or a multi-term INEQUALITY, checking the CONCLUSION (after the last `=>`). Verified:
  held-out-mac `Pr=Pr` → byequiv leads; pr_distinguish `|Pr−Pr|≤` → ler_trans leads.
- **F1 (med)** a no-op commit still printed `**EasyCrypt error:** text-equal` under "there
  is no error to fix". Fixed in `_md_l1_result` (suppress the EC-error line on no-progress).
- **E-BUG2 (med, safe-direction)** `_menu_topics_changed` compared the lean view to the
  saved full audit_view → spurious FULL. Fixed: compare audit_view vs audit_view.

Still open (NOT regressions — pre-existing or lower priority), for follow-up:
- R2 (med): B2 dropped only the `eager` handle; the kept swap/conseq/rnd handles still
  carry relational wording ("before `sim`", "smaller relation", "one side") on single-
  sided goals. Wording-only.
- P1 (med, pre-existing): pr_G4 `sp 2 0` is wrong because the alignment's first setup row
  picks mid-program assigns `[10,12]` — an upstream alignment-partition defect unrelated
  to this session.
- terse-menu submit-shape low: the one-line pointer emits `{"topic":"<one>"}`, but
  `tactic_forms` needs `name` and `call_subgoals` needs `invariant`.
- `_GOAL_NAME_RE` still uses `\b` (drops primes on goal-side op refs) — pre-existing,
  exposed not caused by B8.

## Follow-ups (3 fixed, 1 reverted-as-deeper)
- **R2 FIXED** — `_prhl_surgery_tactic_handles` now varies wording by `two_sided`:
  on single-sided hoare/phoare goals the kept wp/swap/conseq/rnd handles drop the
  relational framing ("before `sim`", "smaller relation", "one side", "pRHL") for
  single-program phrasing; two-sided equiv/pRHL keep the relational wording.
- **terse submit-shape FIXED** — `_md_reference_terse` annotates topics that need an
  extra payload arg: `tactic_forms (+name)`, `call_subgoals (+invariant)`, with an
  explainer, so the one-line pointer stays copy-pasteable.
- **`_GOAL_NAME_RE` FIXED** — trailing `\b`→`(?![A-Za-z0-9_'])` so a goal-side op ref
  like `foo'` keeps its prime (was the last `\b`-after-prime drop, exposed by B8).
- **procedure_straight_line_prefix cap made PER-SIDE** (was a combined cap that could
  starve the right side) — clean robustness fix.
- **P1 NOT fixed (reverted) — still open, deeper than a count swap.** pr_G4 `sp 2 0`
  is wrong (leading prefix is `[1,2,3]` → `sp 3`), but BOTH the alignment (`[10,12]`)
  and the frontend prefix (`[10]`) are measured relative to the chosen `next_frontier`,
  which is a MID-program sample (order 11) rather than the first frontier from the
  current position. The real fix is in `next_frontier` selection / computing a
  leading-from-start prefix for the sp/wp hint — a separate upstream change. The
  attempted count-source swap was lateral (made it `sp 1`), so it was reverted; a
  code NOTE marks the open issue at the absorb-depth builder.

## P1 ROOT-FIXED — the `sp`/`wp` hint was wrong because a regex dropped single-digit program lines
The real root cause (not a count-source issue): for phoare/hoare goals the native
pRHL parser does not apply, so the IR falls back to
`procedure_statements_from_pretty_goal`, whose line regex `\((?P<path>[0-9]…)`
required a digit IMMEDIATELY after `(`. But EasyCrypt right-pads single-digit line
numbers for alignment (`( 1)`…`( 9)`) while two-digit lines are flush (`(10)`), so
EVERY single-digit `( N)` line was silently dropped — the parsed program started at
statement 10, `next_frontier` pointed at a MID-program sample (order 11), and the
`sp`/`wp` absorb count was measured against the wrong frontier (pr_G4: `sp 2`). mee
was unaffected only because it uses the `(1--)` numbering format (no leading space).
Fix: `\(\s*` in the regex (`ec_procedure_frontend.py`). Now the full program is
parsed and `next_frontier` is the FIRST frontier (pr_G4: order 4).

Second half: with the program recovered, the alignment then counted ALL straight-
line assigns before the call (pr_G4: 1,2,3,5,8,10,12 → `sp 7`), but 5/8/10/12 sit
after intervening samples, so `sp 7` would illegally cross them. The body frontend
`procedure_straight_line_prefix` correctly stops at the first sample (`[1,2,3]`). So
the absorb-depth builder now prefers the frontend's LEADING run WHEN it starts at
the program head (order ≤ 1), and falls back to the alignment count only when the
frontend under-parsed an asymmetric two-column setup (its run starts mid-program) —
reconciling pr_G4 (`sp 3`) with the asymmetric-setup regression test (`sp 2 5`).
Verified: pr_G4 `sp 3 0` (next_frontier@4), mee `sp 6 0`, equiv `sp 1 2`, held-out-mac
`sp 2 2`; 1411 tests pass.

## Large-scale cross-validated audit (12 runs, 8 finders, 2 independent verifiers/finding)
A workflow fanned out 8 dimension finders over 12 runs (~190 turns: phoare/hoare/
equiv/pRHL/pr, L1/L4/adaptive, proved+incomplete, MEE / a private held-out MAC
corpus / cramer-shoup / ChaChaPoly),
then had two INDEPENDENT agents per finding (one confirm-vs-raw-EC, one refute-as-
by-design). 12 raw → 6 CONFIRMED, 3 disputed, 3 rejected. All 4 distinct confirmed
issues FIXED:
- **closing-probe mislabel (high, NEW)** `workflow/proof_node_runtime.py::_md_probe_outcome`:
  a probe that would CLOSE all goals had empty `goal_after_probe`, so it fell through
  to "Current Goal (unchanged)" and never told the agent the proof was one commit from
  done. Added the proof-closing case (detected via `goal_after_remaining==0` /
  `goal_after_closed`). Verified: pr_inter t011 → "committing CLOSES the proof".
- **R5 regression (high, MINE)** `workflow/surface_profiles.py`: the `is_ineq` detector
  matched the `<` in `Type variables: <none>` / `<:type>` annotations and checked the
  whole goal (incl. hypotheses like `Hsigma: 0 <= sigma_` above the `----` separator),
  so the Pr opener led with `ler_trans` on a bare `Pr=Pr` equality. Now extracts the
  conclusion BELOW the last `----` separator, strips `Pr[...]` events and `<…>`
  annotations, then tests `<=`/`<`. Verified: held-out-mac `Pr=Pr` → byequiv; pr_distinguish
  `|Pr-Pr|<=` → ler_trans.
- **module procedure as unfoldable op (high, NEW)** `ec_name_resolution.py`: `FinRO.get`
  (a random-oracle procedure called with `<@`) was offered as `rewrite /FinRO.get.` via
  the unqualified-`op get` fallback. Now `<@`-call-site procedure names are excluded.
  Verified: step2_2 t014 unfoldable heads no longer contain FinRO.get.
- **setup row vs sp_hint (med, MY P1 residual)** `session_prover_workspace_view.py`: the
  alignment setup ROW counted all 7 assigns before the call while sp_hint correctly said
  3. New `_leading_contiguous_prefix` trims the setup row to the leading run (stop at the
  first statement-order gap). Verified: pr_G4 t004 setup row = [1,2,3] / "3 setup
  statement(s)" / `sp 3 0` — now consistent. Full suite 1411 passed.

DISPUTED (confirmer vs skeptic split — not fixed, for review):
- step1 `sp 1 0` when the left leading prefix is genuinely empty (first stmt is a
  sample): the sl_n==0 alignment-fallback uses the alignment's 1, crossing the sample.
  Real edge of the P1 reconciliation; skeptic called it by-design.
- step2_2 a rejected (recovery) commit on an early relational turn renders with NO
  inspect menu (neither full nor terse); skeptic called by-design.
- held-out-mac large-goal Surgery panel rendered above the goal (`_goal_is_large>=40`): known
  layout choice; confirmer disagreed it is a bug.

## Adjudication of the 3 disputed findings
- **step1 `sp 1 0` (REAL → FIXED)** `ec_procedure_actions.py`: when the body parser
  finds 0 leading assigns (the side's first statement is itself a frontier — a
  sample/call/loop, e.g. step1's `k <$ dkey` at order 1), the leading prefix is
  genuinely empty, so the sp/wp absorb count is now 0 (no hint emitted) instead of
  falling back to the alignment's mid-program 1 — which produced a misleading `sp 1`
  that would cross the leading sample. Verified: step1 t008 absorb_depth={} / no
  sp_hint; pr_G4 still `sp 3 0`; asymmetric regression test still green.
- **step2_2 no inspect menu on a recovery commit (BY-DESIGN, not fixed)**: step2_2
  is the ADAPTIVE surface. It escalates L1→L4 on stall; the menu first appears at
  turn_014. turn_013 is the last PRE-escalation turn — the rejected commit there is
  what triggers the escalation, which only takes effect on the next turn's surface
  (inspect topics are filtered until escalated). The recovery error banner IS shown.
  This is the adaptive escalation being one turn behind, not a menu-gating defect.
- **held-out-mac focus-above-goal on large goals (BY-DESIGN, not fixed)**: `_goal_is_large`
  (>=40 lines) deliberately leads with the Surgery/decompose map before a long
  two-sided goal (route-before-wall). The cross-checker that defended the code judged
  it intended; the user's "lead" preference was for inspect/lookup answers, not large
  commit goals. Left as a deliberate tradeoff.
