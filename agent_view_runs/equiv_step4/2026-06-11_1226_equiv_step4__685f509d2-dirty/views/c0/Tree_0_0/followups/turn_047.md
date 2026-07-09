## Requested: `lookup_symbol` — perm_filterC

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] perm_filterC (kind: lemma) * In [lemmas or axioms]: lemma perm_filterC ['a]: forall (p : 'a -> bool) (s : 'a list), perm_eq (filter p s ++ filter (predC p) s) s.

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 3)

Type variables: <none>

------------------------------------------------------------------------
forall &2,
  size Mem.lc{2} <= qdec =>
  perm_eq (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}))
```
_…(+5 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `size`
- `Mem.lc`
- `qdec`
- `perm_eq`
- `undup`
- `map`
- `ciphertext`
- `filter`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Memory translation:**
- memories in play: `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **3** · phase `ambient_logic` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `auto => />.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

