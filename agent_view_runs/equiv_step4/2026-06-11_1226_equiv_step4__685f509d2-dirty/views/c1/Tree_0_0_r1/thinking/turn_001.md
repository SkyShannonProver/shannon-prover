# Tree-0.0.r1 · turn 1 · commit_tactic

<!-- session 10e1d06e-4141-455b-9861-d12233633c78 · 2026-06-11T20:32:49.179Z -->

**Intent:** `commit_tactic`  
**Payload:** `by auto => />; smt(drop_nth head_cons mem_nth).`

---

Resuming the equiv_step4 proof. The current goal is the `rcondt{1} 2` side condition: after `n <- head witness l` with `l = drop i ns1` nonempty and all of `ns1` in `ROout.m`, show `(n, C.ofintd 0) \in ROout.m`. Since `head (drop i ns1) = nth witness ns1 i` and `i < size ns1`, membership follows. I'll commit the closing tactic.
