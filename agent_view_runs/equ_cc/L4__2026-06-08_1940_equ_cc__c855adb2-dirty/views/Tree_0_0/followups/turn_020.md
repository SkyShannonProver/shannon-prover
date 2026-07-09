## Requested: `inspect_context` — tactic_forms `rnd`

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

=== `rnd` tactic — argument forms === Current proof mode: ambient Form 1: rnd. Use when: Symmetric random sampling: both sides sample from the same distribution and EC can infer the coupling automatically (usually just identity). Example: rnd. Form 2: rnd (fun s => FWD(s)) (fun s => BWD(s)). Use when: Bijection coupling: the two samples are related by a bijection. Provide forward map and backward map. EC generates a subgoal to show FWD and BWD are mutual inverses. Example: rnd (fun s => s + mask) (fun s => s - mask). Note: THE key technique for game hops that shift/mask random samples. Look for it whenever a sampled value on one side equals the other side's sample plus a deterministic offset. Form 3: rnd{1}. / rnd{2}. Use when: Drop a one-sided sampling that's not present on the other side (dead-code elimination for randoms). Typical: LHS samples something the proof doesn't use, RHS doesn't sample. Example: rnd{1}. (* drop useless LHS sample *) Note: In branch-local pRHL surgery, it is also common to combine a one-sided drop with an aligned sample step, e.g. `rnd{2}; rnd.` when the RHS has an extra instrumentation sample before the shared sample. ⚠️ Common mistake: Using `rnd.`...

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 2)

Type variables: <none>

n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
------------------------------------------------------------------------
```
_…(+48 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Surgery — align or decompose the two sides

**Where:**
- frontier: left side only at `r0 <$ dblock`
- frontier: left side only at `no matching left-side sample at this frontier`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## Status
remaining **2** · phase `relational_program` / `procedure_body`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `sp; wp.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

