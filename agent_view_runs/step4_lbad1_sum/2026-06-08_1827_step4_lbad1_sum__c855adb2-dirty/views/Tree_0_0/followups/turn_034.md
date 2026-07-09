## Requested: `lookup_symbol` — nth_find

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] nth_find (kind: lemma) * In [lemmas or axioms]: lemma nth_find ['a]: forall (z0 : 'a) (p : 'a -> bool) (s : 'a list), has p s => p (nth z0 s (find p s)).

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 2)

Type variables: <none>

&m: {}
HP: forall (E : unit ->
                (glob A) * nonce list * int * int * (nonce, associated_data *
                message * tag) fmap * (tag * tag) list * (nonce * C.counter,
```
_…(+68 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `nth`
- `w1`
- `w2`
- `UFCMA_l.lbad1`
- `hr`

**Visible hypotheses:**
- `HP: forall (E : unit ->`
- `hsz: size UFCMA_l.lbad1{hr} <= qdec`
- `hp: p \in UFCMA_l.lbad1{hr}`
- `hpp: p.`1 = p.`2`
- `hfind: find (fun (p0 : tag * tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} = a`

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **2** · phase `ambient_logic` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `move=> &hr [[hsz [p [hp hpp]]] hfind].` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

