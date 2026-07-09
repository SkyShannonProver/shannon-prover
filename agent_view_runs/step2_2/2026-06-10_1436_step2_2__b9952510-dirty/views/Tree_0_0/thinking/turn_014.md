# Tree-0.0 · turn 14 · undo_last_step

<!-- session 00419e7b-22c2-477c-b7b6-2ff3591b0428 · 2026-06-10T21:42:39.115Z -->

**Intent:** `undo_last_step`  
**Payload:** `(none)`

---

`BNR` isn't the resolved name here. Let me find the actual module/state names in the imported SKE theory.

Key discovery in ske.ec:163: `UFCMA(A, St)` is *definitionally* `CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St)))` — exactly goal 1's LHS program. So `UFCMA_genCC` (which gives `={res}`) proves goal 1 directly via `byequiv UFCMA_genCC`. I over-unfolded with `proc`; let me undo back to the fresh goal-1 state.
