# Tree-0.1 · turn 1 · commit_tactic

<!-- session 7aeb5593-35fc-414f-b9a3-5f44b8b6b9da · 2026-06-25T11:05:56.636Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

I'll start by reading the current workspace view to understand the proof state.

Let me read the latest followup and manager result for the full current context.

This is the start of the proof. Let me read the source file to understand the lemma and the modules involved.

I need to understand the modules. Let me look at the definitions of `Poly`, `OCC`, `IFinRO`, `D`, and `mac`.

Let me look at the FinRO / FullRO library definitions and the chacha_enc analog for the calling pattern.

Let me find the PROM library to understand `FinRO.get` and `RO.get` semantics.

`FinRO.get(x)` returns `oget RO.m.[x]` deterministically (no sampling), and `OCC(IFinRO).cc` returns `oget OCC.gs.[(n,c)]`. With precondition `OCC.gs{1} = RO.m{2}` and `={n,a,c}`, both sides compute the same tag. This should be a straightforward `proc; inline *; auto`. Let me load the MCP tool and start.
