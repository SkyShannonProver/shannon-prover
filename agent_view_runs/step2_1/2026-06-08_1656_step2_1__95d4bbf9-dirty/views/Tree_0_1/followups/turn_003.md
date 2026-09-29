## Requested: `lookup_symbol` — CCA_UFCMA.CCA_CPA_UFCMA

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] CCA_UFCMA.CCA_CPA_UFCMA (kind: lemma) * In [lemmas or axioms]: lemma CCA_CPA_UFCMA: forall (St0 <: StLOrcls{-Mem, -StLSke}), equiv[ St0.init ~ St0.init : true ==> (glob St0){1} = (glob St0){2} /\ res{1} = res{2}] => hoare[ St0.kg : true ==> true ] => forall (A0(O : CCA_Oracles) <: CCA_Adv{-Mem, -StLSke, -St0}), (forall (O <: CCA_Oracles{-A0}), islossless O.enc => islossless O.dec => islossless A0(O).main) => forall &m, Pr[CCA_game(A0, RealOrcls(StLSke(St0))).main() @ &m : res] <= Pr[CPA_game(CCA_CPA_Adv(A0), RealOrcls(StLSke(St0))).main() @ &m : res] + Pr[UFCMA(A0, St0).main() @ &m : exists (c : ciphertext), (c \in Mem.lc) /\ dec StLSke.gs Mem.k c <> None<:plaintext>].

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] <=
Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() @ &m : res] +
```
_…(+4 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Opener — reduce the probability goal

**Goal shape:** a goal relating 3 `Pr[...]` terms

**Reduce with:**
- `apply (ler_trans <mid>)` / `rewrite` a `|·|` norm or `ler_add` step — an order/transitivity move that splits the `|Pr − Pr|` / sum bound into per-term obligations; this comes BEFORE any byequiv/byphoare
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound
- `rewrite (<a Pr (in)equality lemma> &m …)` — replace ONE `Pr[...]` term with an equal one; byequiv/byphoare reduce a single program, but this goal relates several Pr terms, so reduce them one at a time

**Unfoldable heads:**
- `rewrite /dec.` (unfolds `dec`)

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

