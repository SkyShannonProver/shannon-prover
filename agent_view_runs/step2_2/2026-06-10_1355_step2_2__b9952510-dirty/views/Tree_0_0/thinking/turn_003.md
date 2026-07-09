# Tree-0.0 · turn 3 · commit_tactic

<!-- session 0ecb35e0-bd33-4830-b6e0-0f2d764377d8 · 2026-06-10T20:58:54.617Z -->

**Intent:** `commit_tactic`  
**Payload:** `have h2 : Pr[UFCMA(A, St).main() @ &m : exists (c : ciphertext), (c \in Mem.lc) /\ dec StLSke.gs Mem.k c <> None] <= Pr[UFCMA_poly(A, FinRO).main() @ &m : res].`

---

h1 is in context. Now I'll introduce the forgery bound h2 (LHS_b ≤ RHS_b).
