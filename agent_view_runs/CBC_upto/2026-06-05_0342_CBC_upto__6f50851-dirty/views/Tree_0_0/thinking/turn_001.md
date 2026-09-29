# Tree-0.0 · turn 1 · inspect_context

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T10:43:43.542Z -->

**Intent:** `inspect_context`  
**Payload:** `pr_bridge_routes`

---

I'll start by loading the MCP tool schema for the proof manager.

The MCP tool is available. The goal is a classic upto-bad bound:
```
|Pr[CBC_Oracle(PRFi):res] - Pr[CBC_Oracle(Sample):res]| <= Pr[Compute:Compute.bad]
```

I have three key local lemmas: `doublequery_eq` (rewrite each side to `DoubleQuery(F)`), `DQ_Sample_Compute_pr` (Compute.bad = DoubleQuery.bad on Sample), and `DQ_Sample_Compute_eq` (equiv). Let me ask the manager for verified bridge routes and the lemma index before committing.
