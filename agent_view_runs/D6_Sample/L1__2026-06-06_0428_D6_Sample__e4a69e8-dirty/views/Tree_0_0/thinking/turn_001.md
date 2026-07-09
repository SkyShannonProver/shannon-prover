# Tree-0.0 · turn 1 · commit_tactic

<!-- session b3244a16-2444-4a7a-bcc6-185a4960b204 · 2026-06-06T11:29:41.023Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

I'll start by reading the current workspace view to understand the proof state.

Let me look at the source file to understand the modules and lemma.

Let me find the `WhileSamplingFixedTest` theory to understand `SampleWi`.

This is an equiv between two while-loop samplers. `D6.sample` has `while (5<=r)` with `r<-5`, and `D4_6.SampleWi.sample` has `while (!(1<=r<=4))` with `r=5` from the precondition. On the support `[1..6]`, the guards `5<=r` and `!(1<=r<=4)` coincide. So the invariant is `={r} /\ 1<=r<=6`. Let me begin.
