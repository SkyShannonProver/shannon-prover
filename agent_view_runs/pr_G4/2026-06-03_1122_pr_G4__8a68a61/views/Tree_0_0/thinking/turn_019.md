# Tree-0.0 · turn 19 · probe_tactic

<!-- session b9b6df1c-2d45-4f29-b7d5-cce4da2b9fcc · 2026-06-03T18:40:38.359Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc; auto; smt(size_ge0).`

---

`if` needs the conditional as the first instruction; `sp` didn't tee it up as expected. Let me try `auto` to process the whole body (it splits the conditional automatically), then smt for the arithmetic.
