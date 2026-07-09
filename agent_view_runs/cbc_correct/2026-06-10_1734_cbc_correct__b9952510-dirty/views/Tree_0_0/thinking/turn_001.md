# Tree-0.0 · turn 1 · commit_tactic

<!-- session fb95ee9e-ea79-45b2-84b0-617f56eea28d · 2026-06-11T00:35:07.605Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> H.`

---

I'll start by reading the current workspace view to understand the proof state.

Let me read the source file to understand the lemma and its context.

This is the `cbc_correct` lemma (lines 244-249). The goal:
```
cancel (P k) (Pi k) => cbc_dec Pi k st (cbc_enc P k st p) = p
```

My plan: intro the cancel hypothesis, induct on `p` generalizing `st`, then use cancel + IH + boolean-ring `algebra`. Let me load the MCP tool.

I'll commit the intro of the cancel hypothesis.
