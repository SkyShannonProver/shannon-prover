# Tree-0.0 · turn 4 · commit_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T10:47:19.403Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite (doublequery_eq PRFi &m).`

---

The probe was accepted. Let me read the full view to see the post-probe goal.

The probe confirms `doublequery_eq PRFi` rewrites the LHS to `CBC_Oracle(DoubleQuery(PRFi))`. My plan: rewrite both sides to `DoubleQuery(...)`, reverse-rewrite the RHS `Compute.bad` to `DoubleQuery.bad` via `DQ_Sample_Compute_pr`, then close the resulting `|Pr1 - Pr2| <= Pr[bad]` with an upto-bad `byequiv`. The upto-bad tactic form is the genuinely uncertain crux. Let me consult the advisor before committing.

Advisor confirms the route. Let me commit the three rewrites now (all reversible equalities), starting with `doublequery_eq PRFi`.
