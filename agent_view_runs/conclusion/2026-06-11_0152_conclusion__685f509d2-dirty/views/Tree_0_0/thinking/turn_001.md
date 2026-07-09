# Tree-0.0 · turn 1 · lookup_symbol

<!-- session 7e62a6d4-c536-4425-9f12-d7328a869f15 · 2026-06-11T08:53:57.906Z -->

**Intent:** `lookup_symbol`  
**Payload:** `CPA_game`

---

I'm proving the final `conclusion` lemma — the chain is clear from the file: `step2` (CCA ≤ G8 + G9 + Indist gap), `step3` (G8 = CPA/EncRnd), and `step4_1`+`step4_bad2`+`step4_bad1` (G9 ≤ qdec·maxr + qdec·pr1). One naming wrinkle to check first: the goal's second term uses `CCA_game(CCA_CPA_Adv(...), EncRnd)` while `step3` produces `CPA_game(...)` — I need to know whether `CPA_game` is an alias of `CCA_game`.
