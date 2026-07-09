# Tree-0.0 · turn 36 · commit_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:16:23.826Z -->

**Intent:** `commit_tactic`  
**Payload:** `if=> //=.`

---

`if=> //=` produces 3 goals: (1) guard-equality `x∈qs{1} <=> x∈qs{2}` (closable by smt from `={x,qs}`), (2) THEN (bad-flip), (3) ELSE (good sampling). Committing it.
