# Tree-0.0 · turn 18 · commit_tactic

<!-- session e13e9012-11a0-44c0-9ba5-a5d298cc9a0b · 2026-06-10T21:13:54.943Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 2 2 : (={glob A, Mem.lc, Mem.k, RO.m}).`

---

I'll read the latest workspace view to see the current proof state.

I'm continuing a substantial pRHL proof. Let me read the source to understand the right-side program (UFCMA_poly loop) and the key operators before choosing the next tactic.

Let me find the lemma being proven and the key supporting lemmas (UFCMA_genCC, dec, RO definitions).

Let me read the key operator definitions: `dec`, `test_poly`, `mk_rs`, and the RO/FinRO modules.

I now understand the proof. The math: `dec RO.m Mem.k c <> None` means `c.tag = poly1305 r s (topol a cph)` where `(r,s)=mk_rs(oget RO.m.[(c.nonce, ofintd 0)])`; the right loop computes exactly that `(r,s)` for each nonce and `test_poly` detects the match, so `forged` becomes true. Both sides share `init; CCA_CPA_Adv.main`, then the right has the detection loop.

Let me establish the shared-prefix invariant with a `seq` cut.
