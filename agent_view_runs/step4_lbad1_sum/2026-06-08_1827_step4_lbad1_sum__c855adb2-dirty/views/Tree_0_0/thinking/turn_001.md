# Tree-0.0 · turn 1 · commit_tactic

<!-- session 54da74ac-16ac-4ceb-aaab-02957d18342b · 2026-06-09T01:49:07.005Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite -hfind; apply (nth_find (w1,w2) (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} hh).`

---

I'll read my latest workspace view to see the current proof state.

The current goal is `(nth (w1, w2) UFCMA_l.lbad1{hr} a).`1 = (nth (w1, w2) UFCMA_l.lbad1{hr} a).`2` with `hh` (has) and `hfind` (find = a) in context. This is exactly the `nth_find` form already accepted in the spine. Let me load the MCP tool and apply it.
