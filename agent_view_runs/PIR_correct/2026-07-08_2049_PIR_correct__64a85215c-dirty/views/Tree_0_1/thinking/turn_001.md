# Tree-0.1 · turn 1 · commit_tactic

<!-- session dbe52ca4-5aee-47b2-86f1-a4030a610470 · 2026-07-09T03:50:40.202Z -->

**Intent:** `commit_tactic`  
**Payload:** `move => hi.`

---

I'll start proving. The goal is a Pr[...] = 1 statement; the strategy is `byphoare` with a while-loop invariant that `s` and `s'` differ by exactly index `i0`, then XOR-cancellation gives `a i0`. Let me begin.
