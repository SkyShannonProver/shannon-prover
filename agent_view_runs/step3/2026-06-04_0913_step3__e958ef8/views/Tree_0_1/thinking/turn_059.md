# Tree-0.1 · turn 59 · probe_tactic

<!-- session 214c307b-d923-4d2c-a74c-72e428a28c22 · 2026-06-04T16:52:41.938Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc; inline*; auto; rewrite /inv_cpa /=; smt(get_setE mem_set).`

---

Dec obligation. Both `dec` bodies are identical (answered from `Mem.log`, no oracle call), so the invariant is trivially preserved.
