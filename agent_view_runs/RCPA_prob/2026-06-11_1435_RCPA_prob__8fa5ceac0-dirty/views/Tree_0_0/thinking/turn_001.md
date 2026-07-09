# Tree-0.0 · turn 1 · commit_tactic

<!-- session 11ccd487-4cb4-417a-8177-2df4ec1e5f0e · 2026-06-11T21:37:08.364Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv=> //=.`

---

I'll start by reading the current workspace view to see the goal state.

The goal is a Pr-equality between two INDR_CPA games. Let me check the source file for sibling equiv lemmas I can use.

Let me look at the analogous `RCPA_prob_etm` proof (line 432) for structure, and the INDR_CPA game definitions.

The EtM analogue gives the template. Let me check the `MacThenEncrypt` module definition to get the key-pair component order.

Submitting the opening tactic.
