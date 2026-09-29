# Tree-0.0 · turn 47 · probe_tactic

<!-- session 61c51f31-dc55-4d83-a89a-cd3ee77df49c · 2026-06-11T01:07:50.986Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite /predT in H; smt(BBS.big_cons xorwA xorwC xorw0 xorwK).`

---

Case `j <> i0` with both `v` branches. The same recipe should handle the `if v` via smt's internal case split. Let me probe.
