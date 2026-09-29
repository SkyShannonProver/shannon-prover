# Tree-0.1.1 · turn 11 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:36:26.594Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &m0; skip; rewrite /SplitD.test /=; smt(@C).`

---

Side goal: prove `SplitD.test x` holds, i.e. `C.toint (C.ofintd 0) = 0` — true by the `C` subtype roundtrip for the in-range value `0`. Using the discovered idiom.
