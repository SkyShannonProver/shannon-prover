# Tree-0.0 · turn 63 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:10:32.844Z -->

**Intent:** `probe_tactic`  
**Payload:** `move: Hdec; rewrite /dec /genpoly1305 /get /=.`

---

The `Hn0` rewrite fired before the `let` was reduced (so `c.\`1` wasn't present yet). Let me reorder — reduce first, then rewrite `Hgs`/`Hn0`. First probe just the goal beta-reduction.
