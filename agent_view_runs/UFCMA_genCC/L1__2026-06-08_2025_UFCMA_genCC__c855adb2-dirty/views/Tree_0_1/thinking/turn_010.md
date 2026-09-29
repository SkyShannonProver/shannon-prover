# Tree-0.1 · turn 10 · unknown

<!-- session 71eefeb0-ba0c-4a92-8c5d-eb48f1c8df06 · 2026-06-09T04:05:56.259Z -->

**Intent:** ``  
**Payload:** `(none)`

---

The `dec` goal closed. Now the final goal: the main-game `init` prefix plus the trivial adversary-call postcondition bundle. The left `St.init` does `FinRO.init()` and sets `gs <- RO.m`; the right does `FinRO.init()`. I need to know how `FinRO.init` samples (single draw vs. loop) to pick `sim`/`auto` vs. a while-coupling. Let me locate the `FinEager` library.

`FinRO.init` samples the whole finite domain via an identical `while` loop on both sides; the left additionally sets `gs <- RO.m`. The post here bundles a tautological `forall` from the deferred adversary call. Let me first strip that with `conseq` down to the real init postcondition.
