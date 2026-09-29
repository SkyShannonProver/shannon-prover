## Requested: `lookup_symbol` — pr_zeropol

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT-SOURCE] pr_zeropol (kind: op; source-scan fallback) op pr_zeropol : real SOURCE: current context line 1027. NOTE: This is source-scan context because EasyCrypt `print` did not resolve the exact name. Treat it as definition context, not as a daemon-verified lemma signature.

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 9)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
forall &hr,
  ns{hr} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr}) /\
```
_…(+15 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `hr`
- `ns`
- `undup`
- `map`
- `ciphertext`
- `Mem.lc`
- `ns1`
- `filter`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **9** · phase `ambient_logic` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `hoare.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

