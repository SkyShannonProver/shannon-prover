# Tree-0.0 · turn 6 · commit_tactic

<!-- session 0ecb35e0-bd33-4830-b6e0-0f2d764377d8 · 2026-06-10T21:04:32.831Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ha : Pr[UFCMA(A, St).main() @ &m : exists (c : ciphertext), (c \in Mem.lc) /\ dec StLSke.gs Mem.k c <> None] = Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : exists (c : ciphertext), (c \in Mem.lc) /\ dec RO.m Mem.k c <> None].`

---

Now at h2. I'll move the left probability onto the GenChaChaPoly game (via `UFCMA_genCC`), rewriting the event to use `RO.m` (valid since `dec` is `k`-independent and `StLSke.gs = RO.m`).
