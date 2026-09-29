## Requested: `lookup_symbol` — expM

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] expM (kind: lemma) * In [lemmas or axioms]: lemma expM: forall (x : group) (a b : ZModE.exp), x ^ (a * b) = x ^ a ^ b. (* DH.G.expM *) lemma expM: forall (x : group) (k1 k2 : int), x ^ (k1 * k2) = x ^ k1 ^ k2.

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
forall &1 &2,
  (glob A){2} = (glob A){m} /\ (glob A){1} = (glob A){m} =>
```
_…(+21 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `ZModE.exp`
- `dt`
- `result_R`
- `ptxt`
- `A_L`
- `A_R`
- `bool`
- `result_R0`

**Memory translation:**
- memories in play: `{1}`, `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **1** · phase `relational_program` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `auto.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

