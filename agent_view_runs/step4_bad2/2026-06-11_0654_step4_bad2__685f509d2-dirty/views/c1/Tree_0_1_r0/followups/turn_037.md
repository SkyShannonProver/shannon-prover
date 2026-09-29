## Requested: `lookup_symbol` — qdec

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT-SOURCE] qdec (kind: op; source-scan fallback) op qdec : int SOURCE: current context line 1019. NOTE: This is source-scan context because EasyCrypt `print` did not resolve the exact name. Treat it as definition context, not as a daemon-verified lemma signature.

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
forall &hr,
  (UF.forged{hr} = false /\
```
_…(+3 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `hr`
- `UF.forged`
- `UFCMA.bad2`
- `RO.m`
- `empty`
- `nonce`
- `C.counter`
- `poly_in`

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **4** · phase `ambient_logic` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `hoare.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

