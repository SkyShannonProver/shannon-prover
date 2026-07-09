# The Panel-Presentation Contract

The generating function for HOW the agent-facing panel surfaces information — the
rule from which per-block push/pull/suppress decisions are DERIVED, instead of
patched one by one. Hardened by a 4-lens design panel + adversarial synthesis +
a break-it critic (`wf_31784a0e`). The 4-gate architecture survived the critic
structurally; two load-bearing claims were corrected (below).

## Core axiom
The panel is the **compiler half** of a division of labor with a strong autonomous
proof engineer. It supplies, and only supplies, **verified mechanical observations
of the concrete proof state** that the agent cannot cheaply self-produce. Strategy,
route, frontier/inline/glob-framing choices, the semantic invariant *body*, and
naming-intent are the engineer's — the panel never authors them. (Grounding: opus-4-8
hand-authors correct 20-conjunct invariants; the agent's "5 needs" collapse to one —
*"a verified observation of why my held candidate failed."*)

## The decision function — 4 ordered gates (first firing decides; default = SUPPRESS)
For any candidate item at any turn:

- **GATE 0 — MECHANICALLY SOUND & STRUCTURALLY-TRUE-FOR-THIS-GOAL?** (kills 误导)
  The criterion is **SOUNDNESS** (the mechanical claim is TRUE), **not completeness**
  (it need NOT be a closing tactic — a skeleton is sound-but-incomplete by design, since
  the agent fills the semantic body). **The enemy is a GUESS that might be WRONG, not
  "unverified."** The panel's job is useful *mechanical* info; that info is sound when it
  is one of:
  (a) **verbatim prover output** for this state (error text, goal, remaining count) — true;
  (b) **deterministically derived from the goal's actual structure** — the procedure pair
  at the frontier, the statement alignment, the operators present, and **the abstract
  modules AFTER the write-restriction check** (the "module A can write A ⇒ drop ={glob A}"
  rule) — true even if incomplete;
  (c) a **daemon-confirmed-applicable FRAGMENT** — the maximal-accepted-glob frame
  (each `={glob X}` is `try_tactic`-probed; a cheap SOUNDNESS check, NOT "this closes"),
  or a probe result that is a byproduct of the agent's own commit this turn (hooks enabled).
  So the panel does NOT need to daemon-verify a complete tactic to push; it needs the
  mechanical observation to be SOUND. (The skeleton FRAME is push-eligible because it is a
  *true* frame — its applicable form is write-restriction-checked — NOT because "it
  verifies." The skeleton BODY is SUPPRESSED because it is a *guess* at the semantics, NOT
  because it is "unverified.")
  **FAIL ⇒ SUPPRESS the HEURISTIC GUESS** (a guessed invariant body, a "maybe-this-lemma-
  applies", a strategy nudge — content that *might be wrong*).
  Also kill on STRUCTURAL TRUTH: a frame provably wrong for the goal type (two-sided
  surgery on single-sided phoare; `ler_trans` on bare `Pr=Pr`; the hardcoded
  "use eager, NOT swap/call" header on the equiv_fwhile false-block class) → SUPPRESS
  regardless of how produced. *A false fact passes a neutrality check — this gate
  re-derives structural claims against the goal, not tone.*
  **Degradation rule (must be tested):** under `-chain`/hooks-disabled the daemon-fragment
  source (c) is unavailable, so the push channel degrades gracefully to {current_goal,
  raw EC error} ∪ {deterministic-from-structure facts} — a defined, regression-locked state.
  **Anti-laundering:** if part of an item is SOUND and part is a GUESS (skeleton frame vs
  body), SPLIT it and gate the parts separately (never one soundness status over both).

- **GATE 1 — SIDE / SELF-SERVED?** (kills 冗余; the model-aware gate)
  Would *this model* produce this from `current_goal` + its own strategy/semantics,
  this turn, without the panel? STRATEGY / SEMANTIC PAYLOAD / NAVIGATION are agent-side.
  For opus-4-8: self-served ⇒ SUPPRESS (or keep-reachable if also a daemon-verified
  scaffold). **The redundancy instrument is a SHAPE-TYPED build-on metric, NOT
  dotted-name FAIR** (see Broken-Sensor below).

- **GATE 2 — CURSOR-COUPLED / LOAD-BEARING-NOW?** (push vs pull)
  True-by-construction about the current cursor with NO query required, AND bears on the
  agent's currently-held-and-failed candidate (or is the unavoidable primary surface)?
  YES ⇒ PUSH-eligible. Requires the agent to NAME a target (symbol, invariant-to-probe,
  node-to-rewind, navigation) or not-load-bearing-now ⇒ PULL.

- **GATE 3 — PRECISION / FRAMING.** (push throttle; pull admission)
  Only MECHANICALLY-SOUND items push (Gate 0 guarantees — sound, not necessarily a
  complete verified tactic); single-valued honest provenance (ban `daemon=partial` —
  split it); route-neutral framing (states facts/options, prescribes no move,
  self-suppresses with "no candidate here" rather than guessing).

## The push-vs-pull rule
> **PUSH iff** MECHANICALLY-SOUND (Gate 0 — a TRUE observation, possibly incomplete; NOT
> a heuristic guess) **∧** LOAD-BEARING-for-the-held-candidate (or unavoidably-primary)
> **∧** ROUTE-NEUTRAL.
> **PULL** for everything else sound-or-named (offered when its content-presence
> predicate fires; agent opts in).
> **SUPPRESS** for a HEURISTIC GUESS (might be wrong), self-served-for-this-model, or
> wrong-frame.

Verification earns the *right* to push; load-bearing-now earns the *obligation*;
route-neutrality is a veto. All three required (why `call_subgoals` — verified but needs
an agent-supplied invariant — is PULL, not push). **Disposal is SHAPE-AWARE:**
"keep reachable by blind pull" is safe ONLY for name-shaped agent-initiated topics
(`lemma_index`, `lookup_symbol` — the agent knows to ask). For topics the agent must be
TOLD exist (the glob frame, `inv_from_lemma`), blind-pull = NON-recovery → they need a
proactive one-line pointer on the precondition turn (the non-discovery tier).

## Operational definitions (auditable from the saw‖thought‖did triple)
- **有效 / EFFECTIVE** (the only thing that earns PUSH): (i) VERIFIED-correct for this
  goal AND (ii) the agent BUILT ON it — verbatim into a non-rejected commit, OR as a
  mechanical scaffold it extends with its own semantics (the `={glob A,B}` frame is
  有效 even though the agent adds the conjuncts). NOT "literal in final proof" (a
  sub-signal); NOT closure-gated.
- **冗余 / REDUNDANT** (do-not-push): the agent produces equivalent content without the
  panel (self-served / goal-derivable). Net-neutral per instance; a *latency/attention*
  cost in aggregate (NOT a trust breach — see below). Fix = dedupe/de-offer, not delete.
- **误导 / MISLEADING** (kill on sight): (A) wrong/unverified content acted on, OR
  (B) correct content at the WRONG MOMENT / wrong goal-type (the Call-Frontier menu
  mis-framing an eager goal). (B) is the subtle killer — passes a per-item "is it true?"
  check, which is why Gate 0 tests structural truth and Gate 2 tests cursor-coupling.

## Precision mechanism — RE-GROUNDED (critic Attack 3)
The "shared trust budget / cry-wolf discounting" rationale is **DROPPED — the corpus
contradicts it** (pull-rate RISES monotonically with menu size: 0%→6.6%→8.2%→10.3%; a
noisy channel would depress pulls, not raise them). Replaced with the MEASURED rationale:
- The only hard harm in the corpus is **acted-on wrong content (误导)** — a wrong push
  the agent commits. Verified-only-push is justified because it directly prevents THAT,
  not because it guards a trust budget.
- Redundant/menu volume is an **attention/LATENCY** cost (L4 is slower to first-accept),
  not a trust cost. This makes the precision gate stronger and falsifiable, not rhetorical.

## ⚠ The broken value sensor (critic Attack 1/2/5 — blocks the rollout)
Every suppress/keep call rests on a *transfer* measurement, and the current one
(`scorecard.py` FAIR = dotted `Module.proc` name overlap) is **BLIND to frame-, name-,
and syntax-shaped transfer** — it scored a *verbatim* `call (_: ={glob OCC, glob I}).`
commit as a MISS, and `lemma_index`-driven `rewrite (doublequery_eq …)` as a MISS
(FAIR=0/24). So decisions justified by FAIR numbers are unreliable.
**K0 (fix the sensor) is the #1 task, before any fix-rollout or A/B** — re-score
build-on as dotted-name ∥ normalized-substring(frame/tactic) ∥ parse-success(syntax).
This flips one item (skeleton FRAME → PUSH) and removes the false grounds under two
others (tactic_forms, lemma_index were tied/under-counted, not separable by transfer%).

## Model stance — model-aware core + one dial
- **MODEL-INVARIANT** (Gates 0/2/3 + the push floor): "a verified observation of the
  concrete state is always compiler-side and scarce" holds for every model. The error
  gutter is always live.
- **MODEL-DEPENDENT** (Gate 1 only): WHICH derivable content the model self-serves =
  the redundancy threshold + the PULL demand-set. The dial moves items only between
  SUPPRESS and PULL; never demotes a PUSH item, never lifts an unverified one to PUSH.
  opus-4-8 = wide self-serve (suppress skeletons-body/route/nav); a thin model (fable-5:
  169 smt/intro rejects vs opus-4-8's 16) = narrow → low-level discharge scaffolds + the
  skeleton cross BACK to PULL. **The dial CANNOT be calibrated until K0 (the FAIR sensor
  under-credits exactly the frame/bare-tactic scaffolds a weak model needs).**

## Menu / discoverability contract
1. ADMISSION = verified-or-name-exact ∧ answers-a-real-query ∧ content-presence-fires.
   **Content-gated, never syntactic-family-gated** (the family-gate is what produces
   the 65%-offer redundancy + the wrong-moment frame).
2. NO BLIND-GUESS: every admitted topic emits a pre-filled, copy-runnable handle.
   Allowed-but-no-handle = a WIRING BUG (the omission cell — `lemma_index`: wire it).
3. DEAD / double-hop handles removed (`hint`→goal-info 1011/0; stripped `episode_view`;
   `align`→renderer already prints it). Handler stays reachable for blind pull.
4. NEUTRAL set, not ranked recommendation.
5. STABILITY: full menu only on change/recovery/stall; else a one-line pointer.
6. **NON-DISCOVERY TIER** (new): a high-value, daemon-verified, demand-resistant topic
   (the frame; `inv_from_lemma` for a weak model) gets a proactive one-line pointer on
   the precondition turn — reachability ≠ discoverability (agents don't pull what they
   don't know exists; the inv_from_lemma 26-ads→0-pulls lesson).

## The 9 named items (re-ruled after the critic)
| Item | Call |
|---|---|
| raw EC error | **PUSH** (the #1 lever; ~63% of rejects self-correct from it; the `-chain` floor) |
| current_goal | **PUSH** (primary surface) |
| tactic_forms | **PULL**; PUSH only for a parse-verified whitelisted hard idiom (eager inline-binder, 3-arg upto-bad). Separated from the suppressed skeleton body by *parse-provenance, NOT transfer%* |
| lookup_symbol | **PULL** (name-shaped, agent-initiated → blind-pull genuinely safe) |
| call_subgoals | **PULL** (push-ineligible — needs an agent-supplied invariant) |
| call_invariant_skeleton | **FRAME → PUSH-eligible** (daemon-confirmed-this-turn, transfers verbatim); **BODY → SUPPRESS** (heuristic, self-served) |
| call_site_options | **SUPPRESS from push** (误导 #1 wrong-moment menu); content-gate the offer |
| lemma_index | **PULL + WIRE the handle + proactive pointer** (FAIR=0 is a blind spot, not zero value) |
| hint | **SUPPRESS / remove** (1011 offers / 0 pulls, dead dispatch) |

## What's SETTLED vs KNOBS
**Settled (ship-safe):** the 4-gate function; verified-push admission; the 9-item calls;
the menu wiring fixes (kill `hint` ✓done, wire `lemma_index`, content-gate
`call_site_options`, split skeleton frame/body with frame→push, drop `align` offers,
demote `lemma_hints`); honest single-valued provenance.

**Knobs (each with its experiment; metric = faster-to-correct-route, not removal-safety):**
- **K0 [BLOCKS ALL] — fix the transfer sensor** (shape-typed build-on). Hours, no runs.
  Every other K is scored by it.
- **K1 — L4-with-contract vs L4-baseline** on held-out hard lemmas (time-to-first-correct-
  commit, reject-rate vs 9.7% L4 baseline, solve-rate). The whole-contract falsifier.
- **K2 — lean-menu A/B** — re-scoped to a LATENCY hypothesis (leaner menu → faster
  first-accept), since the trust/discounting mechanism is refuted.
- **K3 — static gate vs feedback controller** (defer; circularity risk).
- **K4 — fable-5 dial** (gated on K0).
- ~~K5 trust per-channel vs per-producer~~ — demoted (no discounting measured).

## Open decisions for the human
1. Model-aware vs agnostic shipping (recommend: ship opus core + documented dial; dial
   uncalibratable until K0).
2. Per-firing provenance + ban `daemon=partial` by splitting (required to mark the
   skeleton frame daemon-confirmed-this-turn so Gate 0 can promote it).
3. Staleness SLA for re-deriving the per-model dial.
4. **(the hinge) Accept K0's shape-typed sensor, or accept that every suppress/keep call
   rests on a number that misses verbatim-frame + lemma-name transfer?** Recommend: block
   on K0; ship no suppression justified by dotted-name FAIR until re-scored.

The real wall remains untouched by any panel: **execution stamina** (step4_1 timed out
13/15 *with* the right invariant).
