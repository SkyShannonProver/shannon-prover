# Tree-0.0 · turn 1 · commit_tactic

<!-- session eaf07ef5-71a1-4d41-95c4-abae017c95e5 · 2026-06-09T02:44:27.848Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

I'll start by reading the current workspace view to understand the proof state.

Let me read the latest followup and the source file to understand the lemma context.

I need to find the `equ_cc` lemma in the source file. Let me search for it.

Let me read the `equ_cc` lemma and surrounding context, plus the relevant modules.

This is a complex equiv proof. Let me examine the `ChaCha`, `CCRO`, and related modules to understand the left-hand procedure.

Let me find the `CCRO` module and related RO definitions.

This proof depends heavily on the `Split` library's RO modules. Let me locate that library and understand `RO_DOM`/`RO_Pair` get behavior.

I now understand the key structure: in `enc`, counters are `C.ofintd i` with `i>=1`, so `test=(toint c=0)` is false and `RO_DOM` routes directly to the plain `ROF` RO (the `RO_Pair` layers are only for the `mac`/counter-0 path). Let me gather facts about the counter type, `extend`, `dblock`, and bounds.

Let me check the PROM `RO.get` structure and the `mk_rs`/counter facts to plan the inlining.

I have a clear mathematical picture now. The proof is a relational `proc` over matching while-loops where the left's RO-derived block `z` (routed through `RO_DOM`'s false branch to the plain `ROF` RO, since enc counters are ≥1) is connected to the right's `z <$ dblock` via the involutive XOR one-time-pad bijection `z ↦ extend p +^ z`. Let me load the MCP tool and begin.

I'll start the proof by entering both procedures with `proc`.
