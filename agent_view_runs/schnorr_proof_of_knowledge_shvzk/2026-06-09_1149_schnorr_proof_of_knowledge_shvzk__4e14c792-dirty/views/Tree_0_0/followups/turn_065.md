## Requested: `lookup_symbol` — expM

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] expM (kind: lemma) * In [lemmas or axioms]: lemma expM: forall (x : group) (a b : ZModE.exp), x ^ (a * b) = x ^ a ^ b. (* G.expM *) lemma expM: forall (x : group) (k1 k2 : int), x ^ (k1 * k2) = x ^ k1 ^ k2. [AMBIGUOUS] expM also resolves in 2 other clone instance(s): - G.expM (kind: lemma) (* G.expM *) - GP.expM (kind: lemma) lemma expM: forall (x : group) (a b : ZModE.exp), x ^ (a * b) = x ^ a ^ b. → If your goal references one specifically, use the qualified name. Re-run `-where Foo.expM` to get its body.

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
forall &2 (r1 : ZModE.exp),
```
_…(+11 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `r1`
- `ZModE.exp`
- `dt`
- `challenge`
- `de`
- `w0`
- `\in`

**Memory translation:**
- memories in play: `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **1** · phase `ambient_logic` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `auto => />.` → accepted
- probe `move=> &2 r1 _ eL _; split=> [rR _|_ z1L _]; [by ring | split; [by ring | move=…` → REJECTED: cannot prove goal (strict)
- probe `move=> &2 r1 _ eL _; split=> [rR _|_ z1L _]; [by ring | split; [by ring | move=…` → probed (read-only; state unchanged)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

