# Tree-0.0 · turn 5 · commit_tactic

<!-- session 9380bb3d-763d-4a44-bfcc-de69cee4357c · 2026-06-09T02:44:18.415Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{1}.`

---

The call site is a concrete RO module chain (RO_DOM → RO_Pair → ROF), not an abstract adversary, so I should inline it down to the `ROF.get` sample. Let me inline all left-side calls.
