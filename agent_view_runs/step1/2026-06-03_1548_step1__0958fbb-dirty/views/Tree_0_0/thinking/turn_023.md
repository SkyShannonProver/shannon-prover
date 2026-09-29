# Tree-0.0 · turn 23 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:03:53.107Z -->

**Intent:** `probe_tactic`  
**Payload:** `seq 1 2 : (={glob A} /\ Mem.k{1} = IndBlock.k{2}).`

---

`RealOrcls(S).init = { S.init(); Mem.k <@ S.kg(); }` — so `Mem.k` is the LHS key, sampled `<$ dkey`. RHS samples `IndBlock.k <$ dkey`. The linking invariant is `Mem.k{1} = IndBlock.k{2}`. Plan: `seq 1 2 : (={glob A} /\ Mem.k{1} = IndBlock.k{2})`, then init by coupling the samplings, rest by `call (_: Mem.k{1}=IndBlock.k{2})` discharging enc/dec via `chacha_enc1`/`poly_mac1`. Let me probe the seq cut.
