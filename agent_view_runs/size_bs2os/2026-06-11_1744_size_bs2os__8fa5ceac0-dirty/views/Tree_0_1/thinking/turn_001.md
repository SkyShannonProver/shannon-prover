# Tree-0.1 · turn 1 · commit_tactic

<!-- session c2331656-d559-49bc-b02f-d8920b1d9791 · 2026-06-12T00:45:21.795Z -->

**Intent:** `commit_tactic`  
**Payload:** `elim: bs => [|b bs ih].`

---

I'll read the current workspace view to see the goal state.

`bs2os bs = flatten (map ofblock bs)` and sibling proofs use `size_block` (each block is 16 octets). I'll prove this by induction on `bs`.
