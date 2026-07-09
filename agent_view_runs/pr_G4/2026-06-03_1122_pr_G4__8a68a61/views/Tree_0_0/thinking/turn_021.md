# Tree-0.0 · turn 21 · probe_tactic

<!-- session b9b6df1c-2d45-4f29-b7d5-cce4da2b9fcc · 2026-06-03T18:41:00.061Z -->

**Intent:** `probe_tactic`  
**Payload:** `auto; smt(PKE_.qD_pos).`

---

Now `hoare[1..12 : true ==> I]` — `log` and `cilog` are set to `[]` at stmts 1–2 and untouched after, so `I` reduces to `0 <= 0 /\ 0 <= qD`. Let me probe a closer.
