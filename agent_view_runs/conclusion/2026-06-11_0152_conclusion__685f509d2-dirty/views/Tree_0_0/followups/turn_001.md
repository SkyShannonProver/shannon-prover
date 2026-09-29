## Requested: `lookup_symbol` — CPA_game

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] CPA_game (kind: module) * In [modules]: module CPA_game(A0 : CPA_Adv, O : Oracles) = CCA_game(A0, O).

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Pr[CCA_game(BNR_Adv(A), RealOrcls(ChaChaPoly)).main() @ &m : res] <=
Pr[CCA_game(CCA_CPA_Adv(BNR_Adv(A)), EncRnd).main() @ &m : res] +
```
_…(+3 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Opener — reduce the probability goal

**Goal shape:** a goal relating 4 `Pr[...]` terms

**Reduce with:**
- `apply (ler_trans <mid>)` / `rewrite` a `|·|` norm or `ler_add` step — an order/transitivity move that splits the `|Pr − Pr|` / sum bound into per-term obligations; this comes BEFORE any byequiv/byphoare
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound
- `rewrite (<a Pr (in)equality lemma> &m …)` — replace ONE `Pr[...]` term with an equal one; byequiv/byphoare reduce a single program, but this goal relates several Pr terms, so reduce them one at a time

**Unfoldable heads:**
- `rewrite /pr1_poly_out.` (unfolds `pr1_poly_out`)

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

