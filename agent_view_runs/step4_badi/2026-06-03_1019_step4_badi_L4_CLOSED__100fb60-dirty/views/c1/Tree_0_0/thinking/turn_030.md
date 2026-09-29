# Tree-0.0 · turn 30 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T18:08:29.225Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> _ t0L _ /=.`

---

`split` is asymmetric (carries the first conjunct as a hypothesis). I'll intro the leftover hyp + `t0L`, and use `/=` to simplify the trivial `t0L = t0L` and the `let`, exposing the core conjunction.
