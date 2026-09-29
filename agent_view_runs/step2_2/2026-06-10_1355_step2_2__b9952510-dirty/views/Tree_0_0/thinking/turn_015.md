# Tree-0.0 · turn 15 · commit_tactic

<!-- session 0ecb35e0-bd33-4830-b6e0-0f2d764377d8 · 2026-06-10T21:08:42.016Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv (_: ={glob A} ==> (exists (c : ciphertext), (c \in Mem.lc) /\ dec RO.m Mem.k c <> None){1} => res{2}) => //.`

---

The remaining goal is the core forgery bound: the same GenChaChaPoly game on the left, `UFCMA_poly` (that game + a forge-detection loop) on the right. I'll set it up as a `byequiv` whose postcondition says a successful decryption on the left forces the forge flag on the right.
