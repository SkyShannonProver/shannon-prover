# Tree-0.0 · turn 18 · probe_tactic

<!-- session 7c3d23d4-df62-481f-a000-69153e41b769 · 2026-06-04T08:52:45.638Z -->

**Intent:** `probe_tactic`  
**Payload:** `apply eq_sym; apply (SplitC2.pr_RO_split (G8(A)) (fun _ (r:bool) => r) &m tt).`

---

Now the equality subgoal. Let me probe the proof via `SplitC2.pr_RO_split` (using `eq_sym` so `apply` handles the predicate unification).
