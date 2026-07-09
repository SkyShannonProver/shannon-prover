# Tree-0.1 · turn 15 · commit_tactic

<!-- session a7472aaf-be97-4058-b42c-c8c823c1a2a1 · 2026-06-09T00:03:46.795Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite /get; case: (p{2}) => n a p1 /=.`

---

`enc` unfolded. Now the residual differences: the `let (n,a,p1) = p{2}` destructuring, and `get gs` vs the inlined lambda. Let me unfold `get` and destruct the tuple.
