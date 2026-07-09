# Tree-0.0 · turn 8 · commit_tactic

<!-- session 0ecb35e0-bd33-4830-b6e0-0f2d764377d8 · 2026-06-10T21:06:20.466Z -->

**Intent:** `commit_tactic`  
**Payload:** `have dec_kindep : forall gs (k1 k2 : key) (c : ciphertext), (dec gs k1 c <> None) <=> (dec gs k2 c <> None).`

---

byequiv reduced cleanly to the event-equivalence side goal. The two events differ only in `Mem.k`, and I've confirmed `dec` is `k`-independent. I'll prove a reusable `k`-independence fact, then discharge.
