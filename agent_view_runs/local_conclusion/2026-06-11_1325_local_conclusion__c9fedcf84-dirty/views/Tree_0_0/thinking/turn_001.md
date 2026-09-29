# Tree-0.0 · turn 1 · commit_tactic

<!-- session abd26ef5-2223-44fa-90ae-640e8ee18bd8 · 2026-06-11T20:35:44.777Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite (MtE_security &m) (PtE_security &m) (CBC_security &m).`

---

I'll start by reading the current workspace view to see the proof state.

The goal is a triangle-inequality-style probability bound. Let me examine the source file to find the lemma statement and sibling lemmas I can chain.

Now let me verify the EasyCrypt version's `inline` tactic syntax options (occurrence/codepos selection), since the bridge proof needs selective inlining.

I have a complete plan. Loading the MCP tool schema, then starting to commit.
