# Panel/Producer Registry — the spine of the systematic panel audit

Census run `wf_c7684101-059` (2026-06-24): **122 blocks** across the agent-facing surface
(3 push_always_on, 7 push_conditional, 22 commit_hook, 2 search_hook, 36 pull_inspect_topic,
1 lookup_symbol, 51 analysis_producer). Machine-readable rows: `registry_blocks.json`.
Motivating deep-dive: the CALL surface (see memory `call-panel-root-cause`) — low real-use is
WIRING (good producers exist+allowed+mandated but never offered), not missing content.

## Audit method — the contingency table (3 axes, ternary value)

Every block FIRING is classified on **three axes**; the cells ARE the metric:

- **A. Surfaced**: `pushed` · `in-inspect (pull-offered)` · `computed-but-not-offered` · `not-computed`
- **B. Value** (ternary — NOT "correct"/"对", too vague): `有效 effective` · `无用 useless` · `误导 misleading`
- **C. Consumed**: agent `pulled-&-acted` vs `not`

**B-axis — the division of labor.** The panel/compiler owns the VERIFIED MECHANICAL half; the
agent owns the SEMANTIC half. A block is **有效 (effective)** when its mechanical scaffold is
correct AND the agent built on it — *verbatim OR as a scaffold the agent extends with its own
semantics* (the glob skeleton's `={glob A,B}` frame is 有效 even though the agent adds the
`/\ <conjuncts>` itself). **无用 (useless)** = correct-but-redundant or ignored noise (no help, no
harm). **误导 (misleading)** = wrong AND the agent was led astray (active harm — the thing to KILL).
NOTE: 有效 ≠ "literal content in the final proof" — verbatim-in-proof is the STRONGEST *sub-signal*
of 有效, not its definition; and 有效 does NOT require closure, so it is assessable on the
(mostly-incomplete: corpus is 102 proved / 93 incomplete) hard lemmas where call panels fire most.

**The cells that matter** and what each says about the panel:

| cell (Surfaced · Value · Consumed) | diagnosis | verdict |
|---|---|---|
| in-inspect · 有效 · pulled-it | **contribution** (panel was the agent's source) | KEEP / PROMOTE |
| in-inspect · 有效 · not-pulled | **redundancy** (right, agent self-served) | DEDUPE / better-trigger |
| not-offered · 有效 | **omission cost** (needed, never offered → agent did the work) | **WIRE-IN** |
| in-inspect · 误导 | **active harm** (agent led astray) | **RAISE-PRECISION / DELETE** |
| in-inspect · 无用 | wasted attention + trust-tax | RAISE-PRECISION / DEDUPE |
| 有效 · critical · in-pull-not-push | **placement** (buried in pull) | **PROMOTE pull→push** |

This decomposes panel value into **contribution / redundancy / omission-cost / noise / placement**
— the cross-product, not flat metrics. The central diagnostic is **redundancy vs omission-cost =
demand vs supply**: if the leak is omission-cost (computed-not-offered), fix by WIRING; if it is
redundancy + 误导/无用 (offered but self-served or misleading), fix by PRECISION/TRUST — offering
MORE won't help an agent that has learned to ignore the channel (cry-wolf).

**Measurement (hybrid).** Axes A (Surfaced) + C (Consumed) are DETERMINISTIC from the timeline
(`scorecard.py`: `inspect_topics` = the per-turn offered menu, so absent = never offered; `intent`
= pulls; subsequent commits = acted). The B-axis is **HYBRID**: a deterministic floor (content
verbatim in the final/standing proof = strong 有效) PLUS an agent JUDGMENT over the
**(saw=view ∥ thought=thinking ∥ did=commit)** triple — did the agent's reasoning *build-on* the
correct mechanical scaffold (有效), *ignore* it (无用), or *act-and-go-wrong* (误导)? The
daemon-verified flag is an aux signal for "mechanical half correct". Thinking is joined into
9966/10393 rows.

**Honest floor + discipline.** 有效 still undercounts pure orientation/rule-out value (helping the
agent avoid a path leaves no trace) — so 无用 ≠ "useless to have read"; B is a lower bound. Lessons
baked in: **telemetry-before-source** (source-reading over-weights compute gaps; offer telemetry
reveals wiring gaps — flipped the call verdict A→B); **adversarial verdict non-optional**; **A/B as
gold** where an L1-vs-L4 pair exists; **all goal-classes + structural-truth**; **precision = a
shared trust budget** (noisy blocks tax the good ones).

## (A) OMISSION command-center — topic × profile × offer-mechanism

L1=goal_projection(topics=∅) · L2/L3=signpost · L4d=preview · L4c=UPGRADED_NAVIGATOR · full=all.
`strict−` = removed under `view_neutrality_strict()`. Allow-sets: surface_profiles.py:59-141.

| topic | L4c allowed | offer-mechanism | daemon-verified |
|---|---|---|---|
| goal_info / tactic_forms | ✓ | always_on | yes |
| diagnose / align / checkpoints | ✓ | content_gated | mixed |
| call_subgoals | ✓ | content_gated (3 families) — **PULL-only** | **yes** |
| call_site_options | ✓ | content_gated | no (lightweight) |
| call_invariant_skeleton | ✓ strict− | content_gated | partial (5/77 confirmed) |
| pr_bridge_routes / equiv_bridge_lemmas / lemma_hints | ✓ (some strict−) | content_gated (**probability-family ONLY**) | partial |
| rewrite_candidates | ✓ | content_gated_by_recommendation | **yes** (native AST) |
| **inv_from_lemma** | ✓ | **NEVER offered, 0 prose ← killer** | **yes** (eval-MANDATED) |
| **bridge_probe** | ✓ | **NEVER offered** (1 prose line) | **yes** (the verify step) |
| lemma_index | ✓ | **NEVER offered** (prose only) | **yes** |
| subgoal_gap | ✓ | **NEVER offered** (prose only) | partial |
| proof_frontier | ✓ | **NEVER offered** | yes |
| proof_map / proof_piece / attribution / propose_invariant | ✓ (some strict−) | manager_intercept; never offered as handle | mixed |
| probability_budget_ledger | ✓ strict− | self-handle, double-stripped; no `_inspect_args` case | partial |
| **verified_pivot_options** | **✗ (not in UPGRADED)** | daemon-verified but unreachable from managed profiles | yes |
| **episode_view** | ✗ | **DEAD OFFER** (handle emitted then stripped) | n/a |

## (B) Priority lists this census already exposes

**(B1) Orphan / near-orphan producers — compute value, feed no offered surface:**
- `ec_inv_from_lemma` — invariant template from a lemma, eval-MANDATED, executable via `-inv-from-lemma`; **0 handle-emitters + 0 prose** → blind-guess-only. THE killer pattern (= call).
- `ec_bridge_lemmas` verify arm (`bridge_probe`) — daemon-VERIFY of a Pr bridge; search arm offered, verify companion has 0 emitters. The highest-value/lowest-commission half is invisible.
- `verified_pivot_options` (PivotStrategyPhase `_inspect_verified`) — daemon-verified committable pivots; in NO managed allow-set (CLI-only). Worse than never-offered.
- `ec_call_subgoals` — genuinely daemon-verified; PULL-only, "agent must know to ask".
- `ec_concrete_global_frame` / `ec_call_frontier_structure` / `ec_oracle_diff` — the `={...}` frame, "single biggest measured time sink"; each single-consumer, surfaced UN-verified, single-point-of-failure.
- `ec_proof_ir_liveness` PASS3 — **silently PRUNES computed candidate_menu handles before the agent sees them** (an omission inside the producer; a computed handle vanishes with no trace).

**(B2) Profile-allowed-but-never-offered (UPGRADED_NAVIGATOR, 0 handle-emitters → blind-guess):**
`inv_from_lemma` · `bridge_probe` · `lemma_index` · `subgoal_gap` · `proof_frontier` ·
`proof_map`(handle) · `proof_piece` · `attribution` · `propose_invariant` ·
`probability_budget_ledger` · `verified_pivot_options` · `episode_view`(dead). The two highest-value,
eval-aligned, daemon-verified ones — `inv_from_lemma` + `bridge_probe` — are the exact call repeat.

## (C) Pilot set — validate the harness on 3 diverse axes

1. **inv_from_lemma** (orphan pull-topic) — *the* omission exemplar: L4-allowed + eval-MANDATED +
   daemon-verified + executable, yet 0 offers / 0 prose. Tests the harness's allow-set→0-emitters
   trace + the mandate cross-check + executability proof (`-inv-from-lemma`).
2. **[goal:<type>] commit-hook header** (push-hook) — the cleanest COMMISSION test: a factual
   classifier carrying two HARDCODED directives ("⚠ Use 'eager proc', NOT swap/sim/call"
   session_hooks.py:402-403). Tests structural-TRUTH — re-derive whether the eager directive is
   correct vs a FALSE-BLOCK (memory: equiv_fwhile = eager-blocked-then-works).
3. **call_subgoals** (ec_call_subgoals, daemon-verified pull-only) — the third axis: a real
   `try_tactic` producer, PULL-only, content-gated to 3 families. Tests the daemonVerified column
   (real EC probe vs shape-classification) + the push-vs-pull / family-gating dimension.

Together they exercise all four axes: omission-total (#1), commission-directive (#2),
omission-partial/pull-only-but-verified (#3).

Full census transcript: workflow `wf_c7684101-059`. Per-block source cites in `registry_blocks.json`.
