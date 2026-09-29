## Requested: `lookup_symbol` — enc_eq

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT-SOURCE] enc_eq (kind: equiv · proven; source-scan fallback) equiv enc_eq: _k _p: E.enc ~ E.enc: ={glob E, k, p} /\ k{1} = _k /\ p{1} = _p ==> ={glob E, res} /\ dec _k res{1} = Some _p. SCOPE: `local` — declared `local`, so it is NOT exported; `apply enc_eq` from the current context fails with `unknown identifier`. It is not a usable lemma here. SOURCE: current context line 460. NOTE: This is source-scan context because EasyCrypt `print` did not resolve the exact name. Treat it as definition context, not as a daemon-verified lemma signature. DETAIL: source declaration only; proof body intentionally omitted

## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Pr[INT_CTXT(EtM(E, M), A).main() @ &m : res] <=
Pr[MACa.SUF_CMA.SUF_CMA(M, CMAa(E, A)).main() @ &m : res]
```

## Opener — reduce the probability goal

**Goal shape:** a goal relating 2 `Pr[...]` terms

**Reduce with:**
- `apply (ler_trans <mid>)` / `rewrite` a `|·|` norm or `ler_add` step — an order/transitivity move that splits the `|Pr − Pr|` / sum bound into per-term obligations; this comes BEFORE any byequiv/byphoare
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound
- `rewrite (<a Pr (in)equality lemma> &m …)` — replace ONE `Pr[...]` term with an equal one; byequiv/byphoare reduce a single program, but this goal relates several Pr terms, so reduce them one at a time

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

