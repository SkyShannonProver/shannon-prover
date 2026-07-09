# Panel verdict — opus-4-8, with current-code status

Restricted to **claude-opus-4-8** (149 runs / 6563 turns — the large, strong, dominant model;
the corpus mixes opus-4-6/fable-5 which fail DIFFERENTLY — fable bottlenecks on smt/intro
plumbing, opus-4-8 on exotic technique forms + execution stamina, so the verdict is
model-restricted). Numbers from `scorecard.py --model claude-opus-4-8`. Current-code status
verified at HEAD (read the source, not the bundles — bundles reflect OLDER code).

## The agent (opus-4-8) is a strong strategist + semanticist
It self-authors 20-conjunct relational invariants (correct), picks the route + frontier + inline
depth unaided, and finds names via lookup_symbol. The 5-bucket taxonomy of "needs" largely
COLLAPSES to one: **"give me a verified observation of why my held candidate failed."** It needs
verified MECHANICS + the literal form for a few hard idioms + names — NOT strategy/semantics.
The real wall on hard lemmas is **execution stamina** (step4_1 timed out 13/15 WITH the right
invariant), which no panel fixes.

## USEFUL (keep — verified STILL_PRESENT)
| block | why | current code |
|---|---|---|
| **raw EC error text** | #1 lever; ~63% of 804 rejects carry verbatim EC text → agent self-corrects from the exact string | KEEP |
| goal_info / current_goal | offered 96.5%, the source all else is read against | KEEP |
| tactic_forms (call/conseq/while/seq/transitivity/rnd/swap/sp/wp) | working side-indexed forms the agent can't derive from the goal | KEEP |
| lookup_symbol | exact-name origination, agent completes the rest | KEEP |
| call_subgoals | daemon-verified probe; 75% fair transfer; steers invariant refinement | KEEP |
| diagnose | re-surfaces the full raw EC error | KEEP |

## CURRENT-CODE STATUS — what is still broken TODAY (the actionable output)

**ALREADY FIXED (the 3 highest-leverage; verify-only, do NOT re-touch):**
- **raw EC error text** (USEFUL #1): strip→preserve, all 4 allow-sets keep last_result. Commits 6e6194d8/b66f2994/4dec45a7/6c85b894.
- **CALL_FRONTIER_MENU wrong-moment** (MISLEADING #1): phase-gated on `_frontier_call_count>0`, regression-locked by tests/test_view_neutrality.py:190-205.
- **tactic_forms `eager`** (MISLEADING #2): rewritten by e5a7c655 — working inline-binder is now Form 1, bare `eager while.` marked parse-error. ⚠️ corpus record said STILL_PRESENT — STALE (fix landed inside the corpus window; caught via git log -L). The cautionary tale: reading bundles alone would "fix" an already-fixed entry.

**STILL-BROKEN (all REDUNDANT/GAP, all cheap — fix backlog ranked by leverage × cheapness):**
| # | fix | site |
|---|---|---|
| 1 | **kill `hint` dead topic** (1011 offers, 0 pulls, dispatches to -goal-info) — add "hint" to `_LOW_LEVEL_INSPECT_TOPICS` | session_prover_workspace_view.py:1224-1233 |
| 2 | **wire `lemma_index`** (offered 0, blind-pulled 28× = real demand) — add 1 `_manager_handle` (text in prover_prompt.py:352) | session_prover_workspace_view.py:2349-2597 |
| 3 | content-gate `call_site_options` on `_frontier_call_sites` (65% offer, 17% transfer) | :2384/2457/2510 |
| 4 | drop `align` offer handles (3218 offers, 0.34% pull; renderer already prints side-by-side) | :2451/2539 |
| 5 | demote `lemma_hints` (1760 offers, ~0 pull; one redundant hop before lookup_symbol) | :2728/2934 |
| 6 | gate `pr_bridge_routes` on the producer's pr-count/relation signal (not bare `pr[`) | :2712 + session_workspace_view_manager.py:889 |
| 7 | stop offering `equiv_bridge_lemmas` (unverified blob) by default | :2366 + surface_profiles.py:87 |
| 8 | remove `episode_view` from the menu (DEAD, 0 pulls) | :2317/2570/284 |
| 9 | drop `rewrite_candidates` suggestion line (producer is verified-correct, keep reachable) | surface_profiles.py:98 |
| 10 | `call_invariant_skeleton` default-config offer residue (low priority — deferral text already removed, glob frame now daemon-confirmed) | surface_profiles.py:92 / view_neutrality.py:25 |

All 10 are the same shape (content-gate or menu-drop a per-turn handle). Flipping
`view_neutrality_strict` default ON (view_neutrality.py:25) is one lever for #7/#10/partial-#5,
but does NOT cover #1/#2/#3/#4/#6 (not in the heuristic set) — targeted edits still needed.
Highest single-edit leverage: **#1 (1 line) + #2 (1 handle).**

## RE-SCORE on the fixed shape-typed sensor (K0 `9a61f5fa`) — corrections to the above

The suppress cluster was re-scored on `build_on` (shape-typed) vs the blind dotted-FAIR.
One genuine FLIP + one weakening; the rest hold. (This is why K0 had to precede rollout.)
- **`pr_bridge_routes`: FLIP REDUNDANT→USEFUL/PULL.** pulled 40 (6%, among the highest in
  the cluster), build_on **40%** (dotted-FAIR showed 7% — blind). Do NOT suppress; keep as a
  PULL. The only valid edit is gating the over-trigger (don't offer on bare `pr[`), not removal.
- **`equiv_bridge_lemmas`: WEAKENED.** build_on 0%→**56%** (n=9). Transfer is real, but the
  producer content is UNVERIFIED → the right move is verify-it or keep-as-PULL, NOT "stop
  offering by default."
- `call_site_options` 17%→34%: suppress-from-PUSH holds (wrong-moment menu = 误导) but
  **content-gate, do not delete** (it transfers when pulled).
- `call_invariant_skeleton`: FRAME→PUSH (transfers verbatim, daemon-confirmed-this-turn),
  BODY→SUPPRESS. (per the contract critic.)
- HOLD (low-pull AND low-transfer, or dead, or renderer-duplicated): `align` (0% transfer,
  renderer prints it — drop offers), `episode_view` (0 pulls — remove), `lemma_hints`
  (over-offered — demote, keep reachable), `rewrite_candidates` (verified producer, 1 pull —
  drop suggestion line, keep reachable).
- `lemma_index` (GAP): build_on **46%** (dotted-FAIR was 0/24 — the total blind spot) → WIRE,
  strongly confirmed.

Net change to the backlog: #6 (pr_bridge_routes) becomes "gate the over-trigger, keep the PULL"
NOT "suppress"; #7 (equiv_bridge_lemmas) becomes "verify-or-keep" not "stop offering"; #10
(skeleton) is frame→push + body→suppress; #1/#2/#3/#4/#5/#8/#9 unchanged.

## GAP — built + dispatchable but never offered; do NOT wire
`inv_from_lemma` / `bridge_probe`: offered 0, blind-pulled 0 — DEMAND-RESISTANT for opus-4-8
(it self-authors the invariants these would supply; 26 historical ads of inv_from_lemma → 0 pulls).
Keep as-is. (Opus-4-8-specific; a weaker model might benefit.)

## Honest limits
SAFETY of the removals is high (handlers stay reachable; removing an offer can't break a pull that
wasn't happening). But "the agent self-serves, so the offer is wasted" is INFERRED from
offered-but-not-pulled + trace, NOT counterfactually proven — the UPSIDE (faster-to-correct-route)
is unmeasured. Confirming a fix HELPS needs a small A/B (the "改完测进步" loop), not just removal.
