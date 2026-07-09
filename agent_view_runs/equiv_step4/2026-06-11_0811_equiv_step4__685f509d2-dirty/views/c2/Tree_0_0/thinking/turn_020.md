# Tree-0.0 · turn 20 · commit_tactic

<!-- session 58bd62df-6813-481d-ba03-da6574d86ab1 · 2026-06-11T14:15:00.065Z -->

**Intent:** `commit_tactic`  
**Payload:** `move => &2 hneq hn1 hn2 hm1 hm2 r2L _ t3L _ r4L _ t4L _; rewrite !get_set_sameE get_set_neqE 1:/#; split; [by smt() | by rewrite set_set_neqE 1:/#].`

---

Same pattern — applying the combined rewrite-and-close tactic.
