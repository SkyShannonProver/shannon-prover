# Tree-0.0 · turn 21 · commit_tactic

<!-- session e2cbd3bf-b9d4-4009-a5ab-a91bfa3420b5 · 2026-06-10T22:46:38.465Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ->: Pr[UFCMA_poly(A, FinRO).main() @ &m : res] = Pr[MainD(G5(A), FinRO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.`

---

Now relate `UFCMA_poly(A, FinRO).main` to `G9`. Let me find `UFCMA_poly`'s definition.

`UFCMA_poly` runs `CPA_game(...GenChaChaPoly(CCRO(RO)))` then the forgery loop — structurally `G5 = G4 + G5_end`. To plan the front byequiv I need `CPA_game`/`GenChaChaPoly.kg` definitions and how `FinRO` init aligns (step1 did this manually).

Let me check the `CPA_game` definition to confirm the front aligns with `G5`/`G4`.

The front aligns: both init `FinRO` first, then kg, then `CPA_CCA_Orcls.init`, then `A.main`, then the forgery loop. Converting `UFCMA_poly(A,FinRO).main` to `MainD(G5(A), FinRO).distinguish`.
