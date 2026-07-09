## Requested: `inspect_context` — lemma_index

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

=== PIR.ec: 22 lemma statement(s) (signatures only — proofs are NOT shown) === These are every lemma declared in the current file. Use them to plan which lemmas you can apply/rewrite/bridge with; `lookup_symbol` for the exact declaration of any one before using it. L20 [lemma, top_level] sxor_cons: lemma sxor_cons s i : sxor s (i :: s) i. L23 [lemma, top_level] sxor2_cons: lemma sxor2_cons (s s':int list) (i j:int): sxor2 s s' i => sxor2 (j::s) (j::s') i. L66 [lemma, top_level] PIR_correct: lemma PIR_correct &m i0 : 0 <= i0 < N => Pr [PIR.main(i0) @ &m : res = a i0] = 1%r. L71 [equiv, top_level] PIR_secure1: equiv PIR_secure1: PIR.main ~ PIR.main : true ==> ={PIR.s}. L81 [equiv, top_level] PIR_secure2: equiv PIR_secure2: PIR.main ~ PIR.main : true ==> ={PIR.s'}. L91 [lemma, top_level] PIR_secuity_s_byequiv: lemma PIR_secuity_s_byequiv i1 i2 &m1 &m2 x: Pr[PIR.main(i1) @ &m1 : PIR.s = x] = Pr[PIR.main(i2) @ &m2 : PIR.s = x]. L95 [lemma, top_level] PIR_secuity_s'_byequiv: lemma PIR_secuity_s'_byequiv i1 i2 &m1 &m2 x: Pr[PIR.main(i1) @ &m1 : PIR.s' = x] = Pr[PIR.main(i2) @ &m2 : PIR.s' = x]. L112 [lemma, top_level] restrS: lemma restrS s j : 0 <= j => restr s (j + 1) = (if (j \in s)...

## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
i0: int
------------------------------------------------------------------------
0 <= i0 < N => Pr[PIR.main(i0) @ &m : res = a i0] = 1%r
```

## Opener — reduce the probability goal

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

