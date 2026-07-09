# Tree-0.0 · turn 23 · probe_tactic

<!-- session b9b6df1c-2d45-4f29-b7d5-cce4da2b9fcc · 2026-06-03T18:41:18.805Z -->

**Intent:** `probe_tactic`  
**Payload:** `auto; smt().`

---

This is the hoare suffix `hoare[14..21 : I ==> size cilog <= qD]` — none of these statements touch `cilog`/`log`, and `I` gives `size cilog <= size log <= qD`. Probe a closer.
