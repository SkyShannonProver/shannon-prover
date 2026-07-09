# Tree-0.0 · turn 4 · commit_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T22:50:02.144Z -->

**Intent:** `commit_tactic`  
**Payload:** `have -> : Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] = Pr[CCA_game(A, RealOrcls(OpCCinit.OChaChaPoly(I_stateless))).main() @ &m : res] by byequiv=>//; proc; inline *; sim.`

---

The manager gives a daemon-verified bridge: normalize `ChaChaPoly` → `OChaChaPoly(I_stateless)`. The whole `have -> ... by ...` chain was daemon-accepted, so it's a safe advance. Committing it.
