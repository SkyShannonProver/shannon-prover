# Tree-0.0 · turn 29 · commit_tactic

<!-- session 3ad27182-af4d-4241-bfd6-16292deaeaf6 · 2026-06-04T16:36:46.041Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ha: 1 <= a <= 4 by rewrite hf -h.`

---

smt can't chain the biconditional. Let me derive `ha` deterministically by rewriting with `hf` then `-h`.
