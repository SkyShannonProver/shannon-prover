# Tree-0.0 · turn 27 · commit_tactic

<!-- session 3ad27182-af4d-4241-bfd6-16292deaeaf6 · 2026-06-04T16:35:57.556Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ha: 1 <= a <= 4 by smt(hf); move: (hfinv a ha)=> [_ hB]; rewrite h hB //.`

---

Goal 2: from `h: x = f a`, derive `1<=a<=4` then use `hfinv a`.
