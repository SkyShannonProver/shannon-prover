# Tree-0.0.0 · turn 5 · commit_tactic

<!-- session 2f0c9585-75ee-40a7-b7bd-a964dff75341 · 2026-06-06T11:22:05.143Z -->

**Intent:** `commit_tactic`  
**Payload:** `exists* OCC.gs, k, n, i.`

---

Inline is blocked because `OCC(I)` has an abstract functor argument `I` — EasyCrypt won't inline through it. I'll use the phoare `call` rule instead. First I lift the relevant state with `exists*`.
