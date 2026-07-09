# Tree-0.0 · turn 52 · commit_tactic

<!-- session a8006092-a9db-4441-9330-0fc2cd05aaf8 · 2026-06-10T21:32:34.801Z -->

**Intent:** `commit_tactic`  
**Payload:** `smt(mem_undup map_f take_size take0 size_ge0).`

---

Now at the loop entry/exit logical obligation (remaining 2). The non-trivial facts are: `c \in Mem.lc => c.\`1 \in undup (map fst Mem.lc)` and `take (size ns) ns = ns`. Let me give `smt` the relevant list lemmas.
