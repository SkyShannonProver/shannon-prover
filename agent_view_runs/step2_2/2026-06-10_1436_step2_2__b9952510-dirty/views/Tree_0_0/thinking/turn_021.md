# Tree-0.0 · turn 21 · commit_tactic

<!-- session 00419e7b-22c2-477c-b7b6-2ff3591b0428 · 2026-06-10T21:47:01.201Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv (_: ={glob A} ==> (exists (c:ciphertext), c \in Mem.lc /\ dec StLSke.gs Mem.k c <> None){1} => res{2}).`

---

byequiv accepted, reducing to the equiv `UFCMA(A,St).main ~ UFCMA_poly(A,FinRO).main`. Let me track the plan and commit.
