# Tree-0.0 · turn 16 · probe_tactic

<!-- session b9b6df1c-2d45-4f29-b7d5-cce4da2b9fcc · 2026-06-03T18:39:37.984Z -->

**Intent:** `probe_tactic`  
**Payload:** `call (_: size G3.cilog <= size G1.log /\ size G1.log <= PKE_.qD).`

---

Now `hoare[1..13 : true ==> I]` ending in the `A.choose` call. I'll discharge the call with the invariant `I`. Let me probe the call.
