# Tree-0.0 · turn 13 · commit_tactic

<!-- session b9b6df1c-2d45-4f29-b7d5-cce4da2b9fcc · 2026-06-03T18:37:56.398Z -->

**Intent:** `commit_tactic`  
**Payload:** `conseq (_ : _ ==> (G3.a, G3.a_, G3.c, G3.d) \in G3.cilog) (_ : _ ==> size G3.cilog <= PKE_.qD).`

---

The `conseq` probe is accepted. Let me inspect the preview to confirm it produces the hoare side-goal (`size ≤ qD`) plus the main phoare with the invariant available.

The preview confirms `conseq` splits into: (1) a `hoare[1..21 : true ==> size G3.cilog <= PKE_.qD]` side-goal, and (2) the main phoare bound with the invariant available. This is a `conseq`, not a flagged side-fact `seq`. Committing.
