# Tree-0.0 · turn 22 · commit_tactic

<!-- session e13e9012-11a0-44c0-9ba5-a5d298cc9a0b · 2026-06-10T21:17:35.205Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline *.`

---

The body subgoal is a phoare; I need to know what `FinRO.get` does (whether it's a pure read leaving `RO.m` unchanged). Let me find its definition.

`FinRO` is the eager finite RO (`FinEager`/`FullRO`), so `get` is a pure lookup `oget RO.m.[x]` with no state change. Let me inline it in the body.
