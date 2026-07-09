# Tree-0.0 · turn 39 · probe_tactic

<!-- session 04f2da79-838f-426c-bf2c-64746dff5b0e · 2026-06-10T21:59:50.544Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &hr [[H Hlt] Hz]; case: H => i_rng [Hlc [Hgs [Hns IH]]].`

---

The destructuring works but names are awkward. Let me re-probe with clean nested intro patterns.
