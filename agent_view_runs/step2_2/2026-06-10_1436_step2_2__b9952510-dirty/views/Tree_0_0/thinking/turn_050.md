# Tree-0.0 · turn 50 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:06:24.841Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> [Hn0 | Hold]; last by have := IH c Hc Hdec Hold; smt().`

---

Now peel off the easy IH branch (`c.\`1 \in take i ns` gives `forged{hr}` directly), leaving the `c.\`1 = n0` case.
