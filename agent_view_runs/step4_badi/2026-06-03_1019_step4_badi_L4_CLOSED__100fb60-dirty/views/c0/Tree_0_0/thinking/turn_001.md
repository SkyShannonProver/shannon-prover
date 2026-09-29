# Tree-0.0 · turn 1 · commit_tactic

<!-- session 7d6b85e1-efc5-4558-ab30-99a9e554877b · 2026-06-03T17:20:20.866Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> H.`

---

I'll start by loading the proof intent tool and getting oriented.

Let me analyze the goal. I need to prove a probability bound relating `UFCMA_l.f()` and `UFCMA_li.f(nth0)`. Both run the same `CPA_game(CCA_CPA_Adv(BNR_Adv(A)), O).main()` with oracle `O` that differ only in `set_bad1`. The `badi` event in `{2}` should equal the "nth0-th element of lbad1 has equal components" event in `{1}`.

Let me start by introducing the hypothesis.
