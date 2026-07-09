# Tree-0.1 · turn 14 · probe_tactic

<!-- session 794a61bb-7f1e-4330-b53e-4ab039bb259a · 2026-06-04T08:45:19.727Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite -(SplitC2.pr_RO_split (G8(A)) (fun _ b => b) &m ()).`

---

The `p` predicate needs to be explicit so the `: res` matches `p (glob D0) res`. Providing `p = fun _ b => b`, `&m`, `x0 = ()`:
