# Tree-0.0 · turn 50 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:21:12.041Z -->

**Intent:** `probe_tactic`  
**Payload:** `auto; smt(fdom_set get_set_sameE oget_some).`

---

`fdom_set` is correct. The likely missing piece is `oget_some` (to reduce `oget (Some r0L) = r0L`) — my earlier smt lacked it. Probing with it added.
