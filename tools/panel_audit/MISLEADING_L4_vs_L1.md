# Where did the panel MISLEAD? — the L4-worse-than-L1 investigation

**Question:** in cases where L4 (full panel) did WORSE than L1 (goal+error only), did the
**panel content** mislead the agent — and where? Restricted to **claude-opus-4-8**. Method:
deep-read the `(saw ∥ thought ∥ did)` bundle triple at the divergence for 8 L4-worse lemmas;
synthesis; then an **adversarial critic** that re-derived every load-bearing claim from raw
bundles + the *full* run census (not single A/B pairs) and **overturned two verdicts**. The
numbers below are the **post-critic** (final) ones.

## Headline (survives a hostile read)

**The panel NEVER flipped a proof route.** Mechanism (e) "chased-wrong-route" — the only
mechanism that would justify "the panel misled the agent" — is **absent in all 8 lemmas**,
including the most suspicious (step2_3, where the agent's transitivity-telescope is its *own*
EC reasoning, and the followups' "transitivity" is `ler_trans` real-order, a different tactic).

The panel's real, measurable harm is **(1) latency/dilution** and **(2) exactly one
profile-gated false-block guard**. It is NOT strategic misdirection.

| verdict | original | **FINAL (post-critic)** | lemmas |
|---|---|---|---|
| PANEL_MISLED (route-flip) | 0 | **0** | — |
| MIXED (real co-dominant panel cost) | 3 | **2** | pr_G4 (solid), step2_2 (minor) |
| NOT_PANEL (variance / EC-semantics / affordance) | 5 | **6** | UFCMA_genCC, step2_3, PIR_correct, schnorr, step4_lbad1_sum, **step2_1** |

**The premise is itself shaky.** Full same-commit census: **6 of 8 lemmas, L4 always proved**
— it was just SLOWER, and "slower" is fully explained by the **probe-before-commit affordance
L1 lacks** (probes ~double the turn count: step2_3 51 vs 0, step2_2 69 vs 0, PIR 28 vs 0).
step2_3's L4 actually **beat** L1 on one pair. The true "L4 failed where L1 proved, replicated,
same commit" set is **{pr_G4}** + **{UFCMA_genCC at n=1}** (n=1 = indistinguishable from seed
variance).

## The 3 representative cases — the full spectrum of "did the panel mislead?"

### 1. pr_G4 — YES, the one genuine defect: a route-health guard blocks a CORRECT tactic

This is the **only solid panel-causation in the corpus**, and the deep-read *understated* it.

- **L1 (proved):** committed `seq 13 : (size G3.cilog <= PKE_.qD) 1%r (...) 0%r 1%r.` at its
  t9, EC accepted in **342 ms**, walked to qed (110 turns, 0 probes, 0 inspects).
- **L4 (stalled):** submitted the **byte-identical** tactic at t11. The pushed view
  `views/c0/Tree_0_0/turn_011.json` says verbatim:
  `"kind":"probability_budget_risky_commit_repair"`,
  `"message":"The manager did NOT commit this tactic because route health marks it as risky
  under the product probability budget."`, `"status":"accepted_but_route_risky"`,
  `"primary_next_action":{"intent":"undo_to_checkpoint"}`. **The commit was genuinely
  WITHHELD** (goal `remaining` did not advance). The agent's read ("the manager won't commit
  it and recommends rewinding") is **accurate, not a misperception**.
- **Profile-gated to L4 in source:** `workflow/proof_management/analyzers/route_health.py:677`
  → `transition["profile_gate"] = "l4_checked_action_surface"`. **L1 structurally cannot hit
  this guard.** So this is NOT variance — it is the panel, by construction.
- **The agent's response (contemporaneous, unfakeable):** it spent ~6–8 turns evading a wall
  that EC itself did not raise — `conseq` reshaping (t12, 294 s), and in chunk1 it **bolted a
  tautological reflexive conjunct** `((X)\in G3.cilog) = ((X)\in G3.cilog)` onto the cut purely
  to defeat the guard's string matcher (c1 t18: *"the block is a string-level route-health
  policy. I'll present the same correct cut … so it reads as an event-preservation boundary."*).
- **Second defect, same lemma:** the followups (`followups/turn_008.md`) push a **"⚠️ Deep
  Surgery"** header with **two-sided relational vocabulary** (`rcondt{i}`, `swap [a..b] c`,
  "line up statement order across the **two sides**", sample-coupling `t0{1}=t1{2}`) — on a
  **single-program phoare** goal (`Bound:[<=]…`, `pre=true`, no `{1}/{2}` sides). Structurally
  **false**.
- **Honest limit:** the guard SOLIDLY caused wasted turns + a false blocked-state, but did
  **not** provably cause the timeout (L4 killed at 59t; L1 needed 110t to prove — L4 was nowhere
  near done). **MIXED: panel-causation SOLID, failure-attribution WEAK.**
- **Bonus bug:** the timeline's `result_summary:"accepted commit"` for this withheld commit is
  the **commit-verdict mislabel** bug family again (probe accepted ≠ commit applied).

### 2. step2_2 — minor but real: attention dilution from advertised-but-EMPTY handles

- **L1 (proved):** minimal panel (26 lines). At t1, 0 s overhead, reasoned "A+B≤C+D → split via
  `ler_add`" and committed immediately. First commit **t1 / 0 s**.
- **L4 (proved, slower):** opener view advertised `inspect_lookup_handles` for
  `pr_bridge_routes` ("daemon-verified committable Pr bridge routes"), `equiv_bridge_lemmas`,
  `lemma_hints`, `lemma_index`. The agent **clicked them first** (t1 `lemma_index`, t2
  `pr_bridge_routes`), both **returned empty** (*t3: "No verified bridge routes — I'll construct
  the proof."*), THEN fell back to L1's exact move. First commit slipped to **t4 / 168 s**.
- **Verdict MIXED, but panel is the SMALL contributor:** the real 2-turn opener detour is
  panel-attributable, but the bulk of the gap is 69 probes + a self-diagnosed `while{2}`
  probe-tool bug — both NOT panel.

### 3. step2_1 — INSTRUCTIVE near-miss: the panel showed WRONG content, the agent ignored it

The deep-read called this MIXED/unverified_skeleton; **the critic downgraded it to NOT_PANEL**,
and the downgrade is the interesting part.

- **The wrong content is real:** `views/Tree_0_0/turn_009.json` `/last_result/content/items[0]`
  carries an invariant skeleton lifted from a **completely unrelated development** —
  `call (_: inv_cpa‹ROin.m|ROout.m|ROF.m›{1} … BNR.lenc{1} … UFCMA.cbad1 …)` — with the
  **false rationale** `why: "inv_cpa's parameter types match the in-scope state fields."`
  (a FALSE structural fact passing a neutrality check — the producer matches by type-shape
  across the whole corpus, not by *this goal's scope*).
- **But the agent was NOT misled:** (a) it **solicited** that content (t9 = `inspect_context
  call_invariant_skeleton`) — it was not pushed at the frontier; (b) it dismissed it the same
  turn (t10: *"The skeleton suggestions are **leakage from an unrelated development** … **not
  applicable**. My bridge invariant is simple."*) and committed the correct
  `call (_: ={Mem.k} /\ OpCCRO.OCC.gs{1}=StLSke.gs{2})` at t11 — the same invariant L1 found
  one-shot. Cost ≈ 1 turn.
- **Lesson:** the opus-4-8 agent is **robust to wrong panel content** — it opens a drawer, sees
  junk, closes it. The producer defect is real (and worth fixing) but did not cause harm here.

## The two genuine defects → contract-gate gaps

| defect (where) | severity | gate that should catch it | already prevented? |
|---|---|---|---|
| **route-health/`probability_budget` guard withholds a daemon-accepted commit** (pr_G4) | **HIGH** | **Gate 3 route-neutral** — a surface must surface facts, not *block/prescribe* a route | **NO — NEW GAP.** Gates govern the *offered menu*; this is a **commit-path policy** outside their scope. The probe accepted the tactic; only the commit was intercepted. → **add commit-path neutrality: never withhold/risk-label a tactic the daemon-probe already accepted.** |
| **two-sided "Deep Surgery" header on a single-program phoare goal** (pr_G4) | HIGH | **Gate 0 structural-truth** — asserts `{1}/{2}` sides the goal lacks | **NO** — Gate 0 doesn't run on the route-health header text. → run the side/frontier truth-check on prescriptive headers. |
| **skeleton generator returns off-development candidates with false "types match"** (step2_1) | MED (producer) | **Gate 0** — re-derive that the skeleton's named state vars are in *this* goal's scope | **PARTIAL** — a false "types match" reads as a neutral option and passes. → scope-check named vars before surfacing. |
| **opener handles advertised even when empty** (step2_2, + UFCMA's 21 inspect detours) | MED (pervasive) | **Gate 2 cursor-coupling** — content-gate handles | **NO (soft) GAP** — Gate 2 covers the call-frontier menu (which IS suppressed; PIR t49-51 ignored) but not opener lookup-handles. → don't advertise `pr_bridge_routes`/`equiv_bridge_lemmas`/`lemma_hints` unless they have non-empty daemon-verified content this goal. |

**Net:** the fixed contract already neutralizes the route-misdirection class (mechanism e = 0).
The two genuine gaps are at the **edges the gates don't reach**: commit-path guards (the high-cost
pr_G4 case) and empty-handle advertising (the pervasive dilution). The single highest-value fix is
**the pr_G4 route-health `probability_budget` commit guard** — it is the only place the panel
demonstrably hurt a correct proof.

## Honest limits

1. Small N (8 lemmas, opus-4-8); the load-bearing conclusion rests on **1** clean case (pr_G4)
   + 1 at n=1 (UFCMA). "0 route-flips" = "never observed in this sample," not "impossible."
2. The probe-affordance confound is severe: L4 has `probe_tactic`, L1 doesn't → L4 ~2× turns by
   construction. "L4 slower" is structurally expected and is NOT misdirection evidence.
3. Unrecoverable thinking at several turns (UFCMA Tree-0.1 31/49/51 stored seconds only;
   step4_lbad1_sum origin session absent) — caps confidence on those NOT_PANEL calls (but they
   are absence-of-evidence, and shared-rejection + self-reasoning evidence dominates).
4. pr_G4's failure-vs-slowdown split: the guard SOLIDLY caused turn-waste + a false block; it did
   NOT provably cause the timeout.

## Key bundle references

- pr_G4: `agent_view_runs/pr_G4/2026-06-03_1122_pr_G4_L4_STALLED__100fb60-dirty/views/c0/Tree_0_0/turn_011.json` (the "did NOT commit" message) + `.../thinking/turn_012.md` + `.../c1/Tree_0_0/thinking/turn_018.md` (guard-gaming) + `.../followups/turn_008.md` (Deep-Surgery header); vs `.../2026-06-03_0854_pr_G4_L1_CLOSED__100fb60-dirty/` (342 ms clean commit). Source: `workflow/proof_management/analyzers/route_health.py:677`.
- step2_2: `agent_view_runs/step2_2/2026-06-04_0046_step2_2_L4__ed86503-dirty/views/.../followups/turn_000.md` vs `…L1…`.
- step2_1: `agent_view_runs/step2_1/2026-06-04_0030_step2_1_L4__ed86503-dirty/views/Tree_0_0/turn_009.json` (`/last_result/content/items`) + `.../thinking/turn_010.md`.
