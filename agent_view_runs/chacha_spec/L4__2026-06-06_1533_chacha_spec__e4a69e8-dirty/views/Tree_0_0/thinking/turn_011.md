# Tree-0.0 · turn 11 · commit_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:38:14.834Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> sz; inline OCC(I).cc; wp; skip.`

---

This reduces cleanly to a pure logical implication. The plan for the main equality: substitute `k{hr}=k0, n{hr}=n0, gs{hr}=gs0`, rewrite `-Heq` to expose `c ++ gen_CTR... i p`, apply `gen_CTR_encrypt_bytes_cons` to split it, unfold `take_xor`, and close by `catA`. The variant is `size_drop` + `block_size>0`. Let me commit this forward-substitution step, then work the logical goal.
