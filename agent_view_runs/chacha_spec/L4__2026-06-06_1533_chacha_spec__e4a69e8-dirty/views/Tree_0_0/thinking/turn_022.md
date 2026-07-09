# Tree-0.0 · turn 22 · probe_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:43:42.567Z -->

**Intent:** `probe_tactic`  
**Payload:** `have Hnil: forall (s:block), take_xor [] s = [] by move=> s; rewrite /take_xor /=.`

---

Goal is clean. Now I'll establish the helper `take_xor [] s = []` (needed as the premise of `gen_CTR_encrypt_bytes_cons`). Let me probe it.
