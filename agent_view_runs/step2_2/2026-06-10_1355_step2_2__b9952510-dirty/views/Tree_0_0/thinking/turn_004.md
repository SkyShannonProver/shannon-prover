# Tree-0.0 · turn 4 · commit_tactic

<!-- session 0ecb35e0-bd33-4830-b6e0-0f2d764377d8 · 2026-06-10T20:59:47.474Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv (_: ={glob A} ==> (exists (c : ciphertext), (c \in Mem.lc) /\ dec StLSke.gs Mem.k c <> None){1} => res{2}) => //.`

---

Now the goal is the forgery bound. I'll set it up as a `byequiv` with an implication postcondition (dec-success on the left implies the poly forge flag on the right).
