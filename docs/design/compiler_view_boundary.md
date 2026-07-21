# Compiler View Boundary — Heuristic vs. Mechanical Skeleton

**Status (2026-07-09):** P1–P4 landed; the §3.1 gating spine is deleted from
live code outright (not merely flag-gated). Producer deletion (P3b/P4b) is
partial — the §8 phase table records per-item state. This document is the
design record for the boundary principle; §2 (the FACTUAL / VERIFIED /
HEURISTIC / GATING taxonomy) remains the normative contract.
**Owner:** Shannon Prover
**Scope:** `core/easycrypt/analysis/*`, `core/easycrypt/session_prover_workspace_view.py`,
`core/easycrypt/panel_policy.py`, `workflow/surface_profiles.py`,
`workflow/proof_management/*` (the "proof-state-compiler" view layer).

---

## 1. Motivation

The L4 `ProverWorkspaceView` ("proof-state-compiler view") is supposed to be an
IDE-grade *projection* of the EasyCrypt proof state. In practice it accreted a
thick layer of **heuristic strategy** — route recommendations, confidence
scores, anti-routes, ranked action menus, invariant proposals, a probability
"budget ledger" — and, worse, a layer that **gates commits** on those
heuristics.

The harm is measured, not hypothetical. On lemma `pr_G4` (Cramer–Shoup product
bound), same model (`claude-opus-4-8`), same lemma, same 3 resume chunks:

| run | view | intents | outcome |
|---|---|---|---|
| L1 (`l1_goal_projection`) | bare goal | **107 commit, 2 undo, 0 probe/inspect/lookup** | **PROVED (87 tactics)** |
| L4 (`l4_checked_action_surface`) | rich compiler view | 26 commit, 19 probe, 9 inspect, 6 lookup, 3 undo; final chunk 0 commit | **STALLED (14 tactics)** |

Root cause: the L4 *budget guard* intercepted a daemon-**accepted** `seq` commit
as a "route risk" and replaced it with a repair menu (no working override). The
agent's own thinking: *"the probe was daemon-accepted [but] the manager won't
commit it … No override exists."* The guard's heuristic is a false-positive
generator — L1's winning proof is built entirely from the moves the guard
brands as traps (`seq K : side_cond p1=1%r p2=bound` + per-factor `rnd`).

This violates the project's own boundary (`CLAUDE.md`):

> Treat `decision_context` as **neutral evidence and options, not a command
> list.**

The view became a command list with veto power. This document defines the
boundary precisely, catalogs what is on the wrong side of it, records the
gray zones, and lays out a phased, reversible cleanup.

---

## 2. The boundary principle

Every piece of agent-facing content is exactly one of four classes:

| class | definition | disposition |
|---|---|---|
| **FACTUAL** | deterministically derived from the real EC proof state (goal text, parsed AST/IR, program frontier, symbol/type declarations, name resolution, two-program alignment, read/write/frame facts). "What IS." | **KEEP** |
| **VERIFIED** | heuristic to *generate*, but run through the EC daemon/typechecker and surfaced **only if it actually checks out** (probe accept/reject; daemon-gated bridge routes; maximal accepted glob). | **KEEP** |
| **HEURISTIC** | an un-verified guess about *which move is good/bad* — route recommendations, confidence, anti_routes/unsafe_lowerings, fast_track, ranked suggestions, `likely_proof_family`, relevance-scored lemma hints, invariant proposals, strategy ledgers/plans. | **DELETE** |
| **GATING** | any heuristic that **blocks / vetoes / intercepts / rewinds** a commit or restricts an intent. | **DELETE (first)** |

**Anchor (one sentence):** the view tells the agent *"what is legal here, which
facts must be carried, and what is your decision"* — it never tells the agent
*"which move to make,"* and **nothing heuristic may gate a commit.** Only the
daemon (ground truth) gates.

Guardrails that stay: the `yours` field (names the agent's decision), the
`limitations` field (what the framework cannot tell), and honest
**provenance** stamps (`panel_policy`).

**No advisory-heuristic mode.** Heuristic content is *excluded*, not demoted to
"advisory / shown-but-non-gating." Showing a guess costs attention even when it
cannot gate — pr_G4's paralysis (5–6 min thinks, repeated re-inspects, undo
storms) was the budget *ledger itself*, not only the veto — and a capable model's
own prior beats the heuristic, so advisory heuristic is net-negative noise. The
flag is therefore **binary: neutral (strict ON) vs historic (OFF)**, with no
middle mode. This loses nothing for the A/B: the meaningful comparison is
historic(OFF) vs neutral(ON); a middle "advisory" mode would add the cost without
the signal. (Facts that *read* like help — probe-observed effects, head→tactic
legality, frame must-carry, daemon-verified candidates — are KEPT; they are not
heuristic.)

---

## 3. Audit findings (the research)

Surveyed via 6 parallel subsystem audits over `analysis/*` (~40 files,
>1.5 MB) + `proof_management/*` + the view builder. Cross-checked against a
heuristic-vocabulary frequency scan (top files: `session_prover_workspace_view.py`
166, `ec_proof_ir.py` 84, `surface_profiles.py` 73, `probability_budget.py` 44,
`ec_action_ranker.py` 35, `probability_budget_view.py` 31).

**Headline:** ≈ **8,000 LOC of HEURISTIC/GATING** concentrated in ~20 producers.
LOC figures below are estimates from the audit.

### 3.1 GATING (the active harm) — delete/neutralize first

> **Status 2026-07-09:** the budget-veto spine is gone from live code —
> `probability_budget_view.py` (veto predicate + accepted-probe poisoning),
> the `intent_preflight` commit veto,
> `workspace_view_with_probability_budget_probe_risk`,
> `should_defer_probability_lowering` (deleted with the ranker), and the
> resume route-risk handoff branch (only the structural
> `lost_call_abstraction_boundary` note remains). Still present,
> advisory-only and stripped under strict: the internal
> `probability_budget_route_risk` route-health signal (kept by the §3.2
> scoping decision), the `_phase_legality`/`avoid_action` demotion
> vocabulary, and the rejected-invariant `strategy_hint` resurfacing in
> `session_hook_phases.py` — the latter two fold into the pending P3b/P4b
> deletions. The table below is the original audit, kept as the record.

| component | file:line | role |
|---|---|---|
| `probability_budget_route_risk` (the risk signal) | `core/easycrypt/analysis/probability_budget.py:97-263` | judges a locally-accepted tactic "risky" |
| `route_health` surfacing of the signal | woven into `candidate_moves.route_health`; L4-gated at `workflow/surface_profiles.py:421` | puts the signal in front of the agent |
| `accepted_transition_conflicts_with_probability_budget` (veto predicate) | `workflow/proof_management/probability_budget_view.py:201-421` | decides a commit "conflicts" with the budget |
| **commit veto** | `workflow/proof_management/intent_preflight.py:117-130, 222-241` | replaces `commit_tactic` with a repair `menu` — the tactic is **never sent to the backend** |
| accepted-probe poisoning | `workflow/proof_management/probability_budget_view.py:69-198`; wired `workflow/proof_management/projection.py:133,138` | rewrites a daemon-accepted probe to "accepted_but_route_risky", strips its commit affordance |
| resume handoff note of the risk | `workflow/proof_node_resume.py:882-902` | carries the risk verdict across resume |
| `should_defer_probability_lowering` | `core/easycrypt/analysis/ec_action_ranker.py:332-351, 402-436` | demotes an EC-verified probe to "not the next commit" |
| `_phase_legality` → `avoid` downgrade | `ec_action_contracts.py:270-277` + `ec_action_ranker.py:288-299` | flips a candidate to `avoid_action` on a phase heuristic |
| rejected-invariant resurfacing | `ec_asym_seq_hint.py` + `core/easycrypt/session_hook_phases.py:3472-3507` | re-surfaces daemon-**rejected** invariants as `strategy_hint` |

> Invariant the cleanup establishes: **a daemon-accepted commit is NEVER
> converted to a repair menu.** (See §10.)

### 3.2 Pure HEURISTIC producers — whole / near-whole delete

| producer | file:line | ~LOC |
|---|---|---|
| route-recommendation engine (`_workspace_navigation`, `_navigation_item`, all `_*_navigation`) | `core/easycrypt/session_prover_workspace_view.py:586-627, 721-1976` | ~1000 |
| action scoring/ranking engine | `core/easycrypt/analysis/ec_action_ranker.py` — **PRODUCTION-DEAD (landed, steps 1+2a+2b/1):** Step 1 re-sourced `candidate_moves` from the factual `candidate_menu`; step 2a dropped the heuristic `candidate_rank` menu ordering (keeping only the factual Pr-bridge chain order); step 2b/1 removed the recommendation pipeline from `session_agent_view` and re-sourced the factual signature/declaration lookups + call-invariant inputs from the menu. The ranker no longer reaches the agent. **DELETED (step 2b/2, done):** the ≈47 `test_proof_ir`/`test_ec_proof_diagnostics` "discovery-lens" tests were re-pointed to query `candidate_menu` directly (and 3 pure annotate-ordering tests dropped), then `ec_action_ranker.py` was removed | ~1000 (deleted) |
| goal-pattern → idiom advice catalog | `core/easycrypt/analysis/ec_goal_patterns.py:63-742` | ~700 |
| Pr path planner (cost/authority/readiness/arithmetic_plan/partial_paths/agenda) | `core/easycrypt/analysis/ec_pr_path_planner.py` (whole; no daemon call) | ~700 |
| asymmetric-seq invariant synthesizer | `core/easycrypt/analysis/ec_asym_seq_hint.py` (whole) | ~430 |
| resume route-diversity reorder + route-family scoring | `workflow/proof_management/route_diversity.py` (~250) + `route_family.py` (136) | ~390 |
| Pr strategy-hint plan menus | `core/easycrypt/analysis/ec_pr_actions.py:59-417` | ~360 |
| budget-ledger advice half **(landed)** | `core/easycrypt/analysis/probability_budget.py` — **deleted** the agent-facing advice fields from all 3 `analyze_probability_budget` returns (`anti_routes`, `likely_proof_family`, `side_condition_recipe`) and the ledger's `route_plan`/`allowed_boundary_moves`/`unsafe_lowerings`/`local_measure_cleanup_hints`, plus their 5 generators. **KEPT** the factual Pr-shape (bound/factors/event/event-bound bridge/factor_slots/event_obligations) and the orchestrator `probability_budget_route_risk` route-health signal (decoupled to compute its own anti-routes internally — orchestrator-search heuristic, not agent-facing). The GATING spine + view were already gone (chunk 2a). | **−188** (agent-facing advice; route-risk kept for route-health) |
| invariant "ingredient" palette (scored) | deleted with the retired surface | ~120 |

### 3.3 ENTANGLED — surgical extraction (keep the factual core, cut the layer on top)

| file | KEEP (factual) | DELETE (heuristic) | ~LOC cut |
|---|---|---|---|
| `ec_dataflow_invariant.py` **(P4b landed)** | read/write/liveness/atom extraction, `shared/dataflow_equalities`, `relational_atoms`, carried-precond closure, `conjuncts`, **`suggested_invariant`** (factual `/\`-join, asym_seq-parallel — stripped at the agent boundary by `_HEURISTIC_KEYS`, kept for internal/footprint use), `live_fact_coverage` (footprint) | **only** `confidence` (self-rating) + `obligation_map` (`_call_invariant_obligation_map`: `preferred_closers` + `obligation_completeness`/`closure_plan_complete` self-judgment) — close-read corrected the audit's over-wide list | ~75 |
| `ec_relational_invariant.py` **(P4b: KEEP WHOLE — audit corrected)** | the entire module: predicate sigs / field pool / scope / type-match / `instantiate_predicate`(daemon-filtered downstream)/`ro_domain_side_conditions`(ingredients+idiom shape, asserts no conjunct)/`invariant_shape_palette`(real in-scope predicates, "possibility space, not a recommendation") | **nothing** — module is mechanical-by-design (docstring: "Mechanical here; which predicate is right is the agent's semantic pick; candidates daemon-filtered; never a committed invariant") | 0 |
| `ec_pr_path_diff.py` | module-tree parse + structural diff + lemma inventory | strategy footers + `pivot_applicability` `plan`/`detail`/`_TAG_RANK_TABLE` | ~575 |
| `ec_action_contracts.py` | layer / readiness / missing-slots / obligations / provenance / runnable-safety check | scheduler-role taxonomy + `phase_legality` + `authority_rank` scalar + strategy/avoid vocab | ~200 |
| `ec_goal_parser.py` **(landed)** | structural parser (goal_type / statements / vars / pre-post / prob shape) | **deleted** `_add_guidance` (the `suggested_tactics` lists + the `info.warnings` "Strategy: use X / do NOT use Y" middle-end prose) + `_enrich_with_kb` + the now-dead `ec_tactics.json` loader (`_load_ec_tactics`/`_get_tactic_details`). The biggest agent-facing PULL residue: `goal_info` (a topic the agent pulls every turn) no longer hands back suggested tactics / strategy prose — the agent reads the structure and pulls `tactic_forms <name>` for factual forms | **−257** |
| `ec_proof_ir.py` **(_phase_guidance landed)** | the IR; **confidence downgrades grounded in observed no-progress (`:2569-2679`) are VERIFIED-KEEP**; `_phase_guidance` now returns only the factual `resource_summary` (counts/flags) | **deleted** `_phase_guidance`'s per-layer `prefer`/`avoid` prose + `pr_obligation_primary_strategy` recommendation; dropped the command-summary `phase_prefer`/`phase_avoid`; trimmed the manager `_frontier_checks_for` route-preference prose (kept the epistemic guardrails — runnable≠proven, don't-infer-proof-from-error) | ~95 |
| `ec_program_ir.py` | program diff structure | `suggested_action_family`+confidence, frontier-distance rank, tactic_hint prose | ~150 |
| `ec_procedure_frontend.py` | statement/frontier parse | loop-invariant candidates, residual `closer_template`, prescriptive role prose | ~100 |
| `ec_procedure_actions.py` | (verify) typed procedure facts | ~40 `strategy_hint` ranked menu items + `preferred_sampling_family` + ordering preconditions | ~600–800 |
| `ec_lemma_index.py` | exact `source_declarations_by_name` + EC-native `-where` (VERIFIED) | `semantic_*_candidates` relevance ranking (`game_similarity`, score<3, sort by −score) | ~200 |
| `ec_error_classifier.py` **(landed)** | EC-error attribution (SYNTAX/STRUCTURE classify + `what`/`why` + the `-tactic-forms` grammar-fact pointer) | **deleted** the whole directed-retry nudge generator (`_build_syntax_guidance` + `_build_arity/unknown_id/lemma_form/memory_guidance` + `_arity_full_tactic_variants` + symbol-scan helpers) + the `do_not` "DO NOT abandon" fields + "REQUIRED NEXT ACTION / try these variants" rendering | **−407** (was est. ~80; the *generator* was ~400) |
| `ec_equiv_closers.py` | proc-pair / hypothesis parse | `build_equiv_exact_closers` source-scan closer emission (`ec_ground_truth:False`) | ~57 |
| `ec_abstract_adv_hint.py` | abstract-adversary call-site detection | `canonical_inv_shapes`/`candidate_call_tactics` ("Daemon accepted" is *asserted*, never probed) | ~45 |
| `ec_menu_actions.py` | `-where`/native-AST/ambient-closer lookups | `semantic_pr_bound_menu_items` score-ranked top-3 | ~30 |
| `workflow/surface_profiles.py` focus blocks | mechanical skeleton (see §3.5) | nav-derived `route`/`why_now`/`confidence`/`fast_track`/`avoid`/`repair` in focus | ~120 (P1) |

### 3.4 KEEP — the legitimate compiler (do not touch)

- **VERIFIED islands:** `ec_pr_bridge_frontend.py` (daemon-gated downstream at
  `session_hook_phases.py:1305/1325/1337/1360`); `ec_call_glob_invariant`
  `maximal_accepted_glob` (probe-gated, hook 2099-2163);
  `ec_call_subgoals` count/active-proc preview (daemon `-try`);
  `probe_alternatives.py` (daemon probe results only).
- **FACTUAL backbone:** `ec_goal_parser` (parser core), `ec_proof_ir`,
  `ec_program_ir`, `ec_procedure_frontend`, `ec_name_resolution`,
  `ec_instantiation_binding`, `ec_native_ast_search`, `ec_native_state`,
  `ec_state_diff` (verdict from real metric deltas), `swap_align`
  (factual alignment; routes to `-try`), `ec_pr_canonical`,
  `ec_pr_elaborator`, `ec_concrete_global_frame`, `ec_oracle_diff`,
  `ec_called_proc_body`, `ec_obligation_gap` (lamp-a: flags WHERE, never WHAT).
- **Neutralizer (strengthen):** `panel_policy.py` —
  `attach_provenance`/`_GUARANTEE` (honest daemon/probe/unverified stamps) and
  `enforce`/FRAMING_STRIP (already strips `proof_story`/`risk_map`/imperative
  wording).
- **On-demand fact menu + surface-profile visibility gates** (eval ablation
  scaffolding, not heuristic veto).

### 3.5 Focus blocks (`workflow/surface_profiles.py`) — the per-phase view

The L4 view is assembled per phase (`_assemble_lean_by_phase`) into one of five
focus blocks. Each is a *mechanical skeleton* with a *nav-prescription leak*.
Usefulness is inversely proportional to nav dependence:

| focus | phase | verdict |
|---|---|---|
| `recover_focus` | failure | **mostly KEEP** — head→tactic legality table + rejection fact + evidence + real rewind checkpoints. (The block that fixed thrashing.) Drop `recovery_class` label + `confidence`. |
| `call_focus` | call_site | **KEEP** — frame must-carry / at-risk / probe-observed `preview_effects`. No nav leak. |
| `pure_focus` | pure_logic | **KEEP** — obligation families + evidence + alignment gap. No nav leak. |
| `surgery_focus` (`deep_focus`) | deep_surgery | **half** — keep `where`/`split_points`(coupling blanked)/`toolbox`/`yours`; drop nav `route`/`why_now`/`confidence`/`fast_track`/`avoid`/`repair`. |
| `opener_focus` | opener/prob | **mostly cut** — keep `unfoldable_heads`/`reduce_with`/`yours`; drop budget-ledger `route`/`framework_strategy`/`confidence`/`why_now`/`fast_track`/`avoid`/`pr_shape_facts` (**the pr_G4 屏**). |

**P1 (landed, commit on this branch)** applied exactly the surgery/opener strip +
recover trim; `call_focus`/`pure_focus` untouched.

---

## 4. Where the boundary is unclear (gray zones)

These are the cases the binary FACTUAL/HEURISTIC split does not cleanly decide.
Each is resolved by an explicit rule below (consistent with the §6 decisions).
**This section is the contract for judgment calls during P3/P4.**

1. **Curated mechanical reference vs. state-derived fact.**
   The head→tactic *legality* table (`_HEAD_TACTIC_TABLE`), the static `toolbox`
   / `reduce_with` / `close_with` / `options` lists. These are *curated* (not
   per-goal-derived) but they assert **grammar/legality** ("a divergent `if`
   head can only be reduced by `case`/`rcondt`"; "`invalid first instruction` =
   a side still has code"), not "which move is good." They list FORMS with
   `<...>`/`YOU pick` blanks.
   **Rule → KEEP ("border material", decision 3).** They are EC's reduction
   grammar, demonstrably fixed real thrashing, and contain no preference. Kill
   only the prescriptive *framing* ("experts decompose…", "almost always", "the
   right move").

2. **Heuristic-to-generate but daemon-VERIFIED-before-surfacing.**
   `ec_pr_bridge_frontend` builds `have -> … by byequiv…` chains from
   pattern-matching, but `session_hook_phases` runs each through `batch_try`/
   `try_chain` and surfaces only `accepted` ones.
   **Rule → KEEP as VERIFIED.** The generator may be a guess; the daemon makes
   the *surfaced* object a fact. (This is the "good kind" of guidance.)

3. **Confidence/avoid grounded in OBSERVED EC behavior vs. taste.**
   `ec_proof_ir:2569-2679` downgrades a candidate to low-confidence / `avoid`
   because EC just made *no progress* with it, or because a name is *unresolved*.
   That downgrade is grounded in an observed fact.
   **Rule → KEEP the FACT, DROP the SCORE.** Surface "this tactic made no
   progress when last tried" / "name not resolved" (factual); do **not** surface
   a `confidence: low` scalar or an `avoid_action` that *gates*. A fact the agent
   can act on; not a verdict that steers or blocks.

4. **Detection vs. strategy in the same producer.**
   `ec_probabilistic_vc` / `ec_pr_obligations` / `pure_tail` *detect* obligation
   shapes (bad-event token present, union-bound additive shape, an unconstrained
   post field) — self-labeled `classification_only` — then append a `strategy` /
   `recommended_tactic` / `expected_rule_families` string.
   **Rule → KEEP detection + evidence + NOT-covered; DROP the trailing
   strategy/recommended_tactic string.**

5. **Exact lookup vs. relevance-ranked retrieval (same file).**
   `ec_lemma_index` has both `source_declarations_by_name` / `-where` (exact,
   factual/verified) and `semantic_*_candidates` (fuzzy `game_similarity` score,
   filter `score<3`, sort by −score).
   **Rule → KEEP exact/`-where`; DELETE the relevance ranking.** Ranking by
   guessed relevance is heuristic; exact name resolution is a fact.

6. **Probe-observed effect vs. heuristic risk label.**
   `call_focus.preview_effects` reports "`inline*` here → 47 goals (observed)"
   plus an `observed_risk` token.
   **Rule → KEEP the observed numbers (a probe fact); DROP a free-text risk
   *label* if it editorializes ("dangerous", "avoid").** "47 goals" is a fact;
   "risky" is a verdict.

7. **Factual effect statement vs. ranking fuel.**
   `ec_action_contracts._abstraction_preservation` ("`inline*` lowers
   abstraction; `call` preserves it") is a true IDE-grade effect statement, but
   the curated family lists exist only to feed the ranker.
   **Rule → KEEP the effect statement as a neutral fact note; DELETE it if it
   only ever fed `_abstraction_rank` (i.e. dies with the ranker).** Decide per
   call-site during P4.

8. **A pointer to verification vs. a move recommendation.**
   `swap_align` emits `recommended_action: probe with -try`.
   **Rule → KEEP.** It routes the agent to *check a fact* (`-try`), it does not
   recommend a proof move. "Go verify X" is neutral; "do X" is not.

9. **A neutral schema key that used to carry a verdict.**
   After stripping, `opener_focus` keeps a `route` key whose value is the
   tautology "reduce `Pr[...] <= Pr[...]` to a relational/phoare judgment first."
   **Rule → ALLOWED but flagged.** The value is non-prescriptive framing, not a
   route choice. The §10 neutrality lint matches *prescriptive strings*, not the
   key name, so this passes. (If it reads as a recommendation in review, rename
   the key to `goal_shape`.)

10. **The ChaChaPoly tradeoff (cross-cutting).**
    On `step4_bad1_lbad1`, L4 *helped* by steering the agent off destructive
    `inline*`. That steering is HEURISTIC and will be deleted. But its *factual
    basis* survives: rule 1 (head table notes `inline*` steps into the body) +
    rule 6 (`preview_effects`: "`inline*` → N goals"). The agent still sees
    "`inline*` explodes the goal here" as a **fact**; it is no longer **told**
    "don't." **We accept this tradeoff** (decision recorded §6).

**Meta-rule for any case not listed:** if the content would be *false or
misleading* when the heuristic guesses wrong, it is HEURISTIC → delete. If it
remains *true* regardless (a parse, a daemon result, an observed count, a
legality fact), it is FACTUAL/VERIFIED → keep.

---

## 5. Target view (good but non-overreaching)

A compliant view contains only these panel classes; everything else is excluded.
(Worked per-phase examples of the resulting appearance: **Appendix B**.)

**Included**

- **STATE (always):** `current_goal.lines`, `proof_status`, `last_result`
  (accepted/rejected + reason).
- **MECHANICAL SKELETON (content-gated by phase, factual):** frontier positions
  & two-sided alignment & first-instruction heads; head→legal-tactic table; seq
  split points (coupling blanked); frame ledger (live reads/writes, must-carry,
  dropped-frame facts + exact rewind point); call-site structure (named handle +
  shape + callable/blocker + glob); pure-tail (obligation families + evidence +
  NOT-covered + alignment gap); probe-observed effects; unfoldable heads (+ exact
  unfold tactic); real rewind checkpoints.
- **VERIFIED CANDIDATES (daemon-gated, provenance-stamped):** bridge routes that
  typecheck; maximal accepted glob; probe results. **Unordered, unscored.**
- **ON-DEMAND FACT MENU (pull):** `inspect_context` (goal_info / tactic_forms /
  align / call_subgoals / …), `lookup_symbol`, `-where`.
- **GUARDRAILS:** `yours`, `limitations`, provenance.

**Excluded (never in the view, by lint):** route recommendations,
confidence/why_now, anti_routes/avoid/forbidden/unsafe_lowerings, fast_track_probe,
ranked action / strategy_hint menus, `likely_proof_family`, relevance-scored
lemma suggestions, budget `route_plan`/`framework_strategy`, invariant proposals
(`suggested_invariant`/`witness`/palette), `recovery_class` label. **And nothing
heuristic gates a commit.**

---

## 6. Decisions (recorded)

1. **Reversible first.** Land behind a single feature flag
   (`view_neutrality_strict`, §8); A/B; delete dead code only after validation.
   No big-bang deletion.
2. **Keep VERIFIED + deterministic-static-parse; delete all heuristic.** The one
   surviving form of "suggestion" is a daemon-verified, **unordered, unscored**
   candidate set; everything ranked/scored/guessed goes.
3. **Keep the border material** — the head→tactic legality table and the static
   toolbox/form lists (gray zone 1). They are grammar facts, not preferences.
4. **Accept the ChaChaPoly tradeoff** (gray zone 10): the `inline*` steering goes;
   its factual basis stays.

---

## 7. Feature flag

`view_neutrality_strict` (config/env; resolved once per run, threaded through the
view-assembly + preflight entry points).

- **OFF (default on merge):** current behavior. Zero change on land → safe to
  merge incrementally.
- **ON:** (a) the §10 neutrality filter runs at the single view-assembly
  chokepoint and strips/asserts-absent every excluded key; (b) heavy heuristic
  producers are short-circuited (not computed) so we don't pay to build what we
  strip; (c) `intent_preflight` never converts a daemon-accepted commit into a
  repair menu — the `probability_budget_route_risk` key (and any route-health
  risk text) is itself stripped by (a), so it is not even surfaced as advisory.
- **Rollout:** flip ON for the L4 eval profile → A/B vs. historic L4 on the
  regression ladder + `pr_G4` + `step4_bad1` → once validated, make ON the
  default and delete the OFF path and now-dead producers in a follow-up.

*(2026-07-09: item (c) is now unconditional — the preflight veto and
`probability_budget_view.py` were deleted outright. The flag still defaults
OFF and continues to control only the heuristic-content strip, items (a)
and (b).)*

---

## 8. Phased plan

Each phase is an independently reviewable PR (P3 likely 2–3). Catalog (§3) maps
to phases:

| phase | content | source | ~LOC |
|---|---|---|---|
| **P1** (landed) | focus blocks → skeleton only | §3.5 | −124 |
| **P2 — gating → advisory** (landed) | flag `view_neutrality_strict`: a single guard in `accepted_transition_conflicts_with_probability_budget` neutralizes the commit veto **+** accepted-probe poisoning **+** affordance stripping (all three route through that predicate), plus a no-op guard on `workspace_view_with_probability_budget_probe_risk`. Route-risk stays advisory. **Scoping note:** the ranker-side demotions (`should_defer_probability_lowering`, avoid-downgrade), the advisory resume handoff note, and rejected-invariant resurfacing are *not* commit-vetoes (they reorder/annotate, not block) — they fold into **P3** where the ranker / `asym_seq_hint` are deleted. **Post-P4 note:** the gating module `probability_budget_view.py` has since been deleted outright, making the never-veto invariant unconditional rather than flag-gated. | §3.1 | ~40 + flag |
| **P3 — chokepoint neutrality strip** (landed) | `enforce_view_neutrality` at the single agent-view exit (`_with_profile_meta`) recursively drops `_HEURISTIC_KEYS` when strict — one place neutralizes the whole view regardless of which producer emitted the content. Ships the §9 neutrality lint. Producer deletion deferred to P3b (the strip already makes them invisible under strict). | §3.2 + §9 | ~60 + flag |
| **P3b — delete dead producers** (partial) | **deleted:** the navigation engine (`_workspace_navigation` and the `_*_navigation` family), `ec_action_ranker`, `ec_goal_patterns`, `probability_budget_view` (the whole gating module), and the `probability_budget` heuristic half. **still present (planned):** `ec_pr_path_planner`, `ec_asym_seq_hint`, `route_diversity`/`route_family`, `ec_pr_actions` plan menus | §3.2 | ~5,500 |
| **P4 — airtight the other agent-facing surfaces** (landed) | the P3 strip covers the per-turn workspace view; this closes the surfaces that do *not* pass through it: (a) **inspect topics** — strict mode removes heuristic topics from the intent gate, rendered menu, and prompt advertisement; (b) **resume handoff** — `_route_health_handoff_notes` skips the route-risk branch (keeps the structural `lost_call_abstraction_boundary` one); (c) **prompt** — `_route_health_guidance_for_profile` returns "" and `prover.py` stops injecting `phase prefer/avoid`. | §3 + §4 | ~80 + flag |
| **P4b — entangled-file extraction** (partial) | the chokepoint strip already neutralizes the *agent surface*, so cutting the heuristic layer out of the entangled files is dead-code cleanup, not correctness. **Landed:** `ec_asym_seq_hint` (confidence/rationale/rejected-fallback), `ec_dataflow_invariant` (`confidence` + `obligation_map` deleted; footprint + `suggested_invariant` + `live_fact_coverage` kept), `ec_relational_invariant` (**audit corrected — KEEP WHOLE, mechanical-by-design**), plus the `ec_proof_ir` consumer (dropped obligation-derived cost_factors / closer-recipe preconditions; kept `live_fact_coverage`). Also landed since (see the §3.3 rows so marked): `ec_goal_parser` guidance deletion, `ec_error_classifier` nudge-generator deletion, `ec_proof_ir._phase_guidance` trim. **Remaining (still present in live code):** `ec_pr_path_diff` (`_TAG_RANK_TABLE` + pivot rank), `ec_action_contracts` (`phase_legality` + `authority_rank`), `ec_program_ir` (`suggested_action_family`), `ec_procedure_frontend` (`closer_template`) / `ec_procedure_actions` (`strategy_hint` menu), `ec_lemma_index` semantic ranking, and the systemic `action_type="strategy_hint"` menu-item sweep (chunk 5). | §3.3 + §4 | ~2,500 |
| **P5 — fixate + verify** (guards landed; A/B open) | the §9 guards shipped as tests (`tests/test_view_neutrality.py` — heuristic-key strip + never-veto preflight invariant; `tests/test_panel_policy.py` — provenance; plus `test_prover_view_text_lint` / `test_narrative_safety`). `view_neutrality_strict` still defaults OFF (env `SHANNON_VIEW_NEUTRALITY_STRICT`); the `pr_G4` / `step4_bad1` re-runs and the flag on/off A/B on the regression ladder are not recorded here | §9 | — |

**Consumers to update alongside** (avoid dangling reads): `workflow/agents/prover.py`
(prefer/avoid prompt text, `:2248`), `workflow/tree/policy.py:377`,
`core/easycrypt/commands/inspect_commands.py` (`suggested_tactics` / now
`legacy_shape_tactic_templates`), `workflow/proof_node_resume.py:882-902`
(route-risk handoff), `workflow/proof_node_runtime.py:1533-1537,965-974`
(route_health render + guidance).

---

## 9. Enforceability (so it does not regrow)

Three CI guards turn the boundary from a convention into an invariant:

1. **Neutrality lint (single assembly chokepoint).** The assembled L4 view and
   every `inspect_context` response must contain no excluded key (§5) and no
   prescriptive-string match (regex: `prefer|you should|avoid|do not|try .* first|
   experts |almost always|the right move|recommended`). Extends
   `panel_policy.enforce`/FRAMING_STRIP into a hard test.
2. **Provenance.** `panel_policy.attach_provenance` stamps every panel
   daemon-verified / structural-fact / unverified; a test asserts no panel is
   both *unverified* and *prescriptive*.
3. **Preflight invariant.** A test asserts a daemon-accepted commit is **never**
   converted to a repair menu — for any route-health signal.

---

## 10. Risks & tradeoffs

- **n=1 on the harm.** `pr_G4` is one lemma; `step4_bad1` (ChaChaPoly) went the
  other way. The flag + A/B (§7) is exactly to settle this with data rather than
  one anecdote. The determinant is *"is the heuristic right on this lemma"* ×
  *"does it gate"* — and a sometimes-wrong heuristic must never gate (§2). That
  part is not contingent on n.
- **Capability regression watch.** P3 deletes a lot. A/B on the regression ladder
  must show no lemma that L4 closed and L1 did not now fails. If a *factual*
  signal turns out load-bearing, the flag lets us re-introduce it as a fact
  (not a recommendation).
- **The ChaChaPoly help is partly lost by design** (gray zone 10). Accepted.
- **Don't over-cut the border material** (gray zone 1) — keeping it is decision 3.

---

## 11. Verification

- Unit: §9 guards green; existing `test_surface_profiles` / `test_workspace_view_manager`
  / `test_intent_preflight` / `test_prover_view_text_lint` / `test_narrative_safety` green.
- Behavioral: re-run `pr_G4` L4 (must no longer veto the `seq`/`rnd` descent) and
  `step4_bad1` L4 (must not regress) under flag ON; A/B vs. flag OFF on the
  regression ladder.
- Metric: `workflow/validation/friction_metrics.py` — `inline_star_commits`,
  `goal_explosions`, `first_lowering_index`, fixation, commit-acceptance, and the
  probe/inspect deliberation share, flag ON vs OFF.

---

## Appendix B — View appearance after cleanup (flag ON)

What the agent reads, per phase, once P2–P5 land (rendered markdown preview;
underlying keys in parentheses). The rule throughout: **facts + legality +
`yours`; no route / confidence / avoid; nothing gated.**

### B.1 Opener / probability — `pr_G4`, BEFORE vs AFTER

**BEFORE (the L4 run that stalled):** ~20 KB JSON — `probability_budget_ledger`
(`factor_slots` B1–B4, `event_obligations`), `anti_routes`
(`single_rnd_for_whole_product_budget`, `seq_cut_allocates_product_budget_to_prefix`),
`forbidden_routes`, `unsafe_lowerings`, `confidence: medium`,
`framework_strategy: run_native_pr_search` — the same block repeated 3×. Plus: a
daemon-accepted `seq` commit bounced to a repair menu.

**AFTER:**

```
## Opener — reduce the probability goal
current goal
  Pr[G4.main() @ &m : (G3.a, G3.a_, G3.c, G3.d) \in G3.cilog]
    <= (PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)
proof_status: open · 1 goal · layer pr
last_result: commit `byphoare => //.` accepted

opener_focus
  route: reduce `Pr[...] <= Pr[...]` to a relational/phoare judgment first.
  reduce_with:
    - `byequiv (_: <pre> ==> <post>)` — to a pRHL equiv (most common)
    - `byphoare (_: <pre> ==> <post>)` — to a phoare bound on one program
  unfoldable_heads:
    - `rewrite /G3.d.` (unfolds G3.d)
  yours: the reduction (byequiv vs byphoare), the pre/post, the numeric bound.

inspect ▸ goal_info · tactic_forms · align · pr_bridge_routes (daemon-verified) · lookup_symbol
```

Gone: factor ledger, anti_routes, confidence, framework_strategy. A `seq …
p1=1%r p2=bound` / per-factor `rnd` commit that EC accepts is **committed**, not
bounced. (This is the exact change that lets L4 walk L1's winning path.)

### B.2 Deep surgery (`deep_focus`, seq_cut phase)

```
## ⚠️ Deep Surgery — decompose, don't grind the whole goal
current goal: <pRHL, two sides> · open · 4 goals · layer procedure_body

deep_focus
  where:
    - setup before the frontier (positions 1–4) — absorb with `sp`/`wp`: nap <- p; n0 <- n; …
    - frontier: both sides at `while (p1 <> []) {`
  split_points:
    - `seq 29 36 : (=?).` — split point given; YOU fill the coupling.
  toolbox:
    - `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
    - `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); loop guard: `while(true); auto`.
    - `swap [a..b] c` — line up statement order across the two sides.
    - `wp` / `wp -N -N` — absorb suffix statements before `call`/`sim`.
    - `conseq(:_==> ={<equal vars>})` then `sim`.
    - local `smt(...)` for the residual.
  yours: which condition to `case` on, which way each guard resolves, the coupling, the smt lemmas.
```

Gone: `route: experts decompose this as case_split_then_rcond → smt`, `avoid`,
`confidence`, `fast_track_probe`, `repair_if_fails`. The split *position* stays,
the *coupling* stays blanked.

### B.3 Call frontier (`call_focus`)

```
## Call Frontier — set up the call invariant
call_focus
  situation: candidate named call NOT callable at this frontier yet
             — blocker: `named_handle_not_callable_in_current_view`; step in or write a manual invariant.
  candidate: `UFCMA_genCC` (`call UFCMA_genCC.`)            [structural-fact]
  invariant_must_carry: `={glob A}`, `={RO.m}`              [frame ledger]
  frame_facts_at_risk:
    - `={RO.m}` needed by current_goal but NOT carried by call #5
      → rewind: submit {"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_5_abc"}}
  preview_effects: tactic `inline*` → remaining goals: 47   [probe-observed]
  options:
    - `call (_: <Inv>)` — cross the call with a relational invariant (YOU write `<Inv>`)
    - `inline*` / `proc` — step into the callee body instead
  yours: the invariant predicate; whether to cross (`call`) or step in.
```

`preview_effects: inline* → 47 goals` is a **probe fact** (gray-zone rule 6):
the agent sees the explosion as data; it is never *told* "avoid inline*".

### B.4 Pure logic / tail (`pure_focus`)

```
## Pure Logic — close with smt / rewrite
pure_focus
  goal_shape: ambient logic residual
  obligation_families:
    - `list_membership` — membership over a mapped/filtered list (seen: mem_cat; mapP) (NOT: arithmetic side-goals)
    - `map_projection` — tuple-field projection through `map` (seen: map_f)
  alignment_gap_to_feed_smt: LHS uses `oget log.[n]` where RHS expects `(n,a,c,t) \in lc` — bridge via the lc/log relation.
  close_with:
    - `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
    - `rewrite <eq>` / `move=> <intro>` — normalise first
    - `case (<cond>)` — split a disjunction/membership
  yours: the lemmas for `smt`, the rewrite chain, the case condition.
```

### B.5 Failure recovery (`recover_focus`, after a rejected commit)

```
## ⚠️ Recover — your last committed tactic was REJECTED
recover_focus
  rejected: `sim.` — EasyCrypt rejected the committed tactic. (right instruction list is not empty)
  head_now: head reads left=`while` right=`while` (both_sides_at_while) — find its row below.
  head_to_tactic:                                            [legality table — border material, kept]
    - head `if` (same guard) -> `if`.
    - head `if` (divergent) -> `case: (<cond>)` then `rcondt{i} N`/`rcondf{i} N`.
    - head `while` -> `while (<inv>)`; force the guard; never `while(true)` without a variant.
    - head `x <- e` -> `sp`/`wp`.   · head `x <$ d` -> `rnd`.
    - head `call` -> `call (<inv>)`, or `inline*`/`proc` to step in.
    - `invalid first instruction` = a side STILL HAS CODE: reduce the head first.
  rewind_targets:
    - `Before call invariant #8` → submit {"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_8_xyz"}}
  yours: match your head to a row, then YOU pick the condition/branch/invariant.
         Do NOT retry the same family that was just rejected.
```

Gone: `diagnosis: wrong_first_instruction` (heuristic class label), `confidence`.
Kept: the rejection fact, the *legality* table (gray-zone 1), real checkpoints.

### B.6 Plain / simple goal — bare core

```
current goal: `x{1} = x{2} => …` · open · 1 goal
last_result: commit `auto.` accepted
inspect ▸ goal_info · tactic_forms · align · lookup_symbol
```

No focus block at all — like L1. When no skeleton signal is content-gated in,
the view collapses to goal + status + last_result + the on-demand menu.

### B.7 Verified candidates (only when daemon-confirmed)

```
verified_bridges (daemon-verified · committable):
  - `have -> : Pr[...] = Pr[...] by byequiv=>//; proc; inline*; sim.`   [daemon-accepted]
  (unordered, unscored; each independently typechecked. If none pass: "no verified bridge route".)
```

The single surviving form of "suggestion": facts the daemon already accepted,
**unordered and unscored**, each provenance-stamped.

---

## Appendix — commit lineage

- P1: `refactor(view): strip heuristic route prescription from L4 focus blocks`.
- P2: `feat(view): view_neutrality_strict flag — gating spine becomes advisory`.
- P3: `feat(view): enforce_view_neutrality — strip heuristic keys at the single
  agent-view exit`.
- P4: `feat(view): airtight the other agent surfaces — inspect topics, resume
  notes, prompt guidance`.
