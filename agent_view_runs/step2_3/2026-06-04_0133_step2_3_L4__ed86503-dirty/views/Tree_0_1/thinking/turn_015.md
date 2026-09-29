# Tree-0.1 · turn 15 · probe_tactic

<!-- session 794a61bb-7f1e-4330-b53e-4ab039bb259a · 2026-06-04T08:46:34.676Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite -(SplitC2.pr_RO_split (G8(A)) (fun _ b => b) &m ()) /=.`

---

Accepted. Let me view the resulting goal.

The rewrite works but leaves a non-beta-reduced predicate wrapper. Let me probe adding `/=` to beta-reduce it back to `res`.
