# Inspect-return quality — quantitative fix list (opus-4-8)

What each `inspect_context` topic actually RETURNS to the agent, and whether the agent
builds on it. Method: a deterministic pass over EVERY opus-4-8 pull (`inspect_quality.py`
— resolves each return followup, tags `empty%` by distinctive phrases, computes `build_on`
via the K0 sensor) + an LLM ground-truth pass (`wf_3591e269`) that tags a ~10-example
sample per topic into useful / empty / placeholder / incomplete / wrong_shape + used, which
the deterministic patterns cannot tell apart.

## Ranked fix list

`useless% = (empty+placeholder+incomplete+wrong)/n` · `fix_priority = total_pulls × useless%`

| # | topic | pulls | useful% | useless% | **used%** | fix_pri | dominant failure |
|---|---|---:|---:|---:|---:|---:|---|
| 1 | **pr_bridge_routes** | 40 | 0% | 100% | **0%** | 40.0 | typed-bridge frontend never derives a route → every pull "no bridge" or `<pre> ==> <post>` |
| 2 | **diagnose** | 49 | 30% | 70% | 31% | 34.3 | returns "No errors found" after a read-only PROBE (only reflects committed transitions) |
| 3 | **call_invariant_skeleton** | 33 | 0% | 100% | **0%** | 33.0 | doesn't emit the real `={glob}` frame; emits an off-development type-match grab-bag |
| 4 | **call_site_options** | 39 | 30% | 70% | 31% | 27.3 | no callee/invariant at a real frontier; bare-goal or smt panel when no frontier |
| 5 | **tactic_forms** | 47 | 50% | 50% | **80%** | 23.5 | **pure preview TRUNCATION** — content is good, cut at Form 4 |
| 6 | **lemma_index** | 28 | 20% | 80% | 10% | 22.4 | truncation drops needed lemmas (51 → ~9); echoes goal-as-lemma |
| 7 | equiv_bridge_lemmas | 12 | 0% | 100% | 0% | 12.0 | all-empty (already demoted from the offer) |
| 8 | **call_subgoals** | 24 | 60% | 40% | **60%** | 9.6 | **no return defect — the TEMPLATE, do not fix** |

## Fix spec per producer (what GOOD looks like)

- **pr_bridge_routes / equiv_bridge_lemmas** — name the daemon-verified/candidate bridge with
  exact signature (e.g. `rewrite (Bridge_Games_eq sigma q &m)`, `rewrite doublequery_eq`), or a
  goal-specific skeleton with the coupling filled from shared globals
  (`byequiv (_: ={glob A, glob EPRF, arg} ==> ={IND.bad} /\ (!IND.bad{2} => ={res}))`), NOT
  `(_: <pre> ==> <post>)`. Fallback floor: surface the local `lemma_index` entries whose
  endpoints type-match the two Pr programs. (`analyze_bridge_lemmas_from_session` already
  produces named lemmas — the preview carries none of it = a WIRING fix.)
- **diagnose** — distinguish three layers: (1) probe-harness/sanitizer rejection ("blocked by
  the probe dry-run, not EC; commit for a real verdict"), (2) EC parse error + arg-form fix
  (drop the L1/session_cli shell-escaping branch under the manager boundary), (3) EC semantic
  rejection (the current good path). NEVER return "No errors found" after a read-only probe.
- **call_invariant_skeleton** — compute the glob frame FROM THIS GOAL's module expressions
  (`A(Log(LRO))` → `={glob Log, glob LRO}`), pre-assembled into a ready `call (_: ={glob ...}).`.
  When sides differ, name THOSE in-scope fields + the per-field correspondence + which carries
  the eager preseed — never a grab-bag of every same-typed clone field.
- **call_site_options** — exact callee+signature, a concrete invariant frame from pre/post, a
  daemon-checked committable form; GATE it (say so + route elsewhere when there is no call
  frontier, never emit a bare goal or the smt panel).
- **tactic_forms** — KEEP (content is right, 80% used). Narrow fix: (1) never truncate the form
  list (the cut form — `call` upto-bad 3-arg, `eager` Form 4 — is disproportionately the one
  needed); (2) goal-aware ordering (lead with the form matching the proof mode); (3) keep one
  instantiated example.
- **lemma_index** — every name + full signature, no mid-list/mid-signature truncation; redirect
  when the file's only lemma is the goal; optionally flag goal-matching symbols.
- **call_subgoals** — PRESERVE as the template (daemon-verified-this-goal). Optional reach win:
  seed it from in-scope predicates so it can bootstrap + verify an invariant in one pull.

## Cross-cutting themes

1. **Truncation is a recurring root cause** (tactic_forms, lemma_index): good content cut at the
   preview boundary, hiding exactly what the agent pulled for. Cheapest universal lever.
2. **The producing analyzers already exist — the gap is WIRING/preview**, not missing capability
   (pr_bridge's named lemmas, the goal-computable glob frame). Echoes the old call-panel
   root-cause: low real-use is wiring, not compiler-missing-content.
3. **call_subgoals is the only template that works** (verified-against-the-live-goal). Every fix
   = make the others more like it: goal-scoped, daemon-verified, exact, complete.
4. **diagnose's empty-after-probe is a probe-amplifier** — it FORCES an extra probe→commit cycle
   (agent probes → "no errors" → must commit just to get a diagnosable error). Highest anti-probe
   leverage; converts a probe into a verdict.

## Honest limits

n≈10/topic vs totals 12–49; rates are point estimates (±~15pts for the mixed topics; the
100%-useless topics are directionally robust at 0/30 usefuls). `empty%` (deterministic) is
reliable; `placeholder%` was over-counted on angle-brackets and the LLM pass re-classified the
mass into empty (bridge) / wrong_shape+incomplete (call); truncation is invisible to the
deterministic pass (LLM-only, from cutoff markers).
