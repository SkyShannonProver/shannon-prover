## Requested: `lookup_symbol` — ROIN.FullEager.RO_LRO_D

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] ROIN.FullEager.RO_LRO_D (kind: lemma) * In [lemmas or axioms]: (* FullEager.RO_LRO_D *) local lemma RO_LRO_D: forall (D0(G : RO) <: RO_Distinguisher{-RO, -FRO}), (forall (_ : nonce * C.counter), is_lossless dpoly_in) => equiv[ D0(RO).distinguish ~ D0(LRO).distinguish : (glob D0){1} = (glob D0){2} /\ RO.m{1} = RO.m{2} /\ arg{1} = arg{2} ==> res{1} = res{2} /\ (glob D0){1} = (glob D0){2}].

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

