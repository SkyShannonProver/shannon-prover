## Requested: `lookup_symbol` — step2

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] step2 (kind: lemma · admit) * In [lemmas or axioms]: local lemma step2: forall (A0(O : CCA_Oracles) <: CCA_Adv{-Mem, -FullRO.RO, -FullRO.FRO, -IndBlock, -OpCCinit.OCC, -OpCCRO.OCC, -CCA_UFCMA.StLSke, -Split0.IdealAll.RO, -SplitD.ROT.RO, -SplitD.ROF.RO, -SplitC1.I1.RO, -SplitC1.I2.RO, -Split1.IdealAll.RO, -SplitC2.I1.RO, -SplitC2.I2.RO}), (forall (O <: CCA_Oracles{-A0}), islossless O.enc => islossless O.dec => islossless A0(O).main) => forall &m, Pr[CCA_game(A0, RealOrcls(ChaChaPoly)).main() @ &m : res] <= Pr[Split1.IdealAll.MainD(G8(A0), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish () @ &m : res] + Pr[Split1.IdealAll.MainD(G9(A0), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish () @ &m : res] + (Pr[Indist.Distinguish(D(A0), IndBlock).game() @ &m : res] - Pr[Indist.Distinguish(D(A0), IndRO).game() @ &m : res]). PROOF STATUS: `admit` — this lemma is declared but its proof body is `admit.` in the in-scope source (still citable in EC; you would be relying on an unproven obligation). SCOPE: `exported_after_section` — exported once its `section` closes, abstracted over the section's declared parameters (supply them, e.g. the adversary module, when...

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

