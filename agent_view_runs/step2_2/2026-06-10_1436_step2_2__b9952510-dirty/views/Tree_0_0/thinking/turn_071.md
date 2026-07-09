# Tree-0.0 · turn 71 · commit_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:14:35.878Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> forged_R i_R; split; first by move=> [hb _] hsz; smt().`

---

Termination closed. Committing, then the exit part (`i_R = size ns` ⇒ `take i_R ns = ns`, and `c.\`1 \in ns` via `mem_undup`/`mapP`).
