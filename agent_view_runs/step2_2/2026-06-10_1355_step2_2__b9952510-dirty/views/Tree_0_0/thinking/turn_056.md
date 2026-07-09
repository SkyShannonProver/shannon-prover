# Tree-0.0 · turn 56 · commit_tactic

<!-- session a8006092-a9db-4441-9330-0fc2cd05aaf8 · 2026-06-10T21:35:14.912Z -->

**Intent:** `commit_tactic`  
**Payload:** `smt(mem_undup map_f take_size take0 size_ge0).`

---

`move` won't introduce the memory quantifiers here. Let me just hand the whole logical goal to `smt` with the list lemmas it needs (`map_f`, `mem_undup`, `take_size`).
