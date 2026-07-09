## Requested: `lookup_symbol` — big_count

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] big_count (kind: lemma) * In [lemmas or axioms]: lemma big_count ['a]: forall (P : 'a -> bool) (s : 'a list), BIA.big P (fun (x : 'a) => count (pred1 x) s) (undup s) = size (filter P s).

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 5)

Type variables: <none>

&m: {}
&hr: {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list, r : poly_in,
     t : poly_out}
szlc: size Mem.lc{hr} <= qdec
```
_…(+16 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `BRA.big`
- `predT`
- `nonce`
- `size`
- `filter`
- `ciphertext`
- `Mem.lc`
- `hr`

**Visible hypotheses:**
- `szlc: size Mem.lc{hr} <= qdec`
- `nE: BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{hr})`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **5** · phase `ambient_logic` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `rewrite nE -BRA.bigEM.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

