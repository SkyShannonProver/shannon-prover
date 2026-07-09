# Tree-0.0 · turn 5 · undo_last_step

<!-- session a51e628e-7b92-45c6-b528-b64183d9b981 · 2026-06-10T22:31:45.549Z -->

**Intent:** `undo_last_step`  
**Payload:** `(none)`

---

This is the core simulation goal. Before committing more tactics, I need to understand the RO plumbing — `CCRO`, `FinRO`, `GenChaChaPoly`, the `Split0` clones, `test`, and `pr_RO_FinRO_D`. Let me read those definitions.

Now I understand the full layering. This is a deep multi-layer split-RO reduction: LHS uses an **eager** `FinRO`, RHS uses **lazy** split ROs, so I can't bridge with `sim` alone — I need `pr_RO_FinRO_D` (eager→lazy) plus the `pr_RO_split` library lemmas. My current byequiv goal (eager-vs-lazy) is unprovable by `sim`, so the Pr-level have-chain is the right path. Let me check `pr_RO_FinRO_D`'s exact signature first.

`pr_RO_FinRO_D` is a section lemma. step1 called it as `pr_RO_FinRO_D h_dout G2 &m () (...)` (with a losslessness hyp first), so the section likely has a `declare axiom`. Let me read the FinEager section to get the exact argument order.

I now have the exact `pr_RO_FinRO_D` signature (takes a `dout` losslessness hyp, then `D`, `&m`, `x`, `p`). The full proof is a multi-layer split-RO reduction chain. For the first structural step I need `GenChaChaPoly`, `RealOrcls`, and `CCA_game`'s `main`. Let me read those.

This is a large, multi-layer reduction. I need `CCA_game` and `RealOrcls` definitions to do the first structural step. Let me find them.

I've confirmed the first structural step works (both sides reduce to identical code calling `A` with the same oracle wrapper). The full proof is a ~8-step split-RO reduction chain per term. My current byequiv goal mixes eager `FinRO` with lazy split ROs (unprovable by `sim`), so I'll work at the Pr level instead. Let me undo the byequiv.
