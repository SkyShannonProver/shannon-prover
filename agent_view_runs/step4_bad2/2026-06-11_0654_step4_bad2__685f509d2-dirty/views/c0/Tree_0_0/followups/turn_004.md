## Requested: `lookup_symbol` — ROIN.RO_LRO_D

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-MISS] ROIN.RO_LRO_D not found. tried: ROIN.RO_LRO_D, MB.ROIN.RO_LRO_D, NonceCount.ROIN.RO_LRO_D, Poly_in.ROIN.RO_LRO_D, Poly_out.ROIN.RO_LRO_D, TPoly.ROIN.RO_LRO_D, Extra_block.ROIN.RO_LRO_D, Block.ROIN.RO_LRO_D, FiniteRO.ROIN.RO_LRO_D, Indist.ROIN.RO_LRO_D, OpCCinit.ROIN.RO_LRO_D, OpCCRO.ROIN.RO_LRO_D, CCA_UFCMA.ROIN.RO_LRO_D, Split0.ROIN.RO_LRO_D, SplitD.ROIN.RO_LRO_D, SplitC1.ROIN.RO_LRO_D, Split1.ROIN.RO_LRO_D, SplitC2.ROIN.RO_LRO_D, IPNonce.ROIN.RO_LRO_D, Byte.ROIN.RO_LRO_D, Key.ROIN.RO_LRO_D, Nonce.ROIN.RO_LRO_D, C.ROIN.RO_LRO_D, MB.I1.ROIN.RO_LRO_D, MB.I2.ROIN.RO_LRO_D, MB.RO.ROIN.RO_LRO_D, MB.RO_Pair.ROIN.RO_LRO_D, MB.ROF.ROIN.RO_LRO_D, MB.ROin.ROIN.RO_LRO_D, MB.ROout.ROIN.RO_LRO_D, NonceCount.I1.ROIN.RO_LRO_D hint: no declaration resolved in the current EasyCrypt context or source-scan fallback. Use a more exact qualified name, or ask the manager for `goal_info` / `lemma_hints` before trying to apply it.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Pr[UFCMA3(RO).distinguish() @ &m : res] <=
qdec%r * maxr pr_zeropol pr1_poly_out
[386|check]>
```

## Opener — reduce the probability goal

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound

**Unfoldable heads:**
- `rewrite /pr1_poly_out.` (unfolds `pr1_poly_out`)

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `byequiv equiv_step4 => // /#.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

