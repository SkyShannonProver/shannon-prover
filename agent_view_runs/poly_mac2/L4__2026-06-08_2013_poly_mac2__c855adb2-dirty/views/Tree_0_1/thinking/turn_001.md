# Tree-0.1 · turn 1 · commit_tactic

<!-- session a3ddb182-07e9-470e-ae4e-baae322329a8 · 2026-06-09T03:13:54.820Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

I'll start by understanding the proof structure. Both `mac` procedures call a deterministic map-lookup (OCC.cc vs FinRO.get) then do identical computation, so inlining should make them align under the precondition `OCC.gs{1} = RO.m{2}`.

Let me load the MCP tool.

I'll start by entering the procedure.
