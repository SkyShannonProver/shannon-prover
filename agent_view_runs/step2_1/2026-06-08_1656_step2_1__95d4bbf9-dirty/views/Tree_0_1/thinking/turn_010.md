# Tree-0.1 · turn 10 · commit_tactic

<!-- session a7472aaf-be97-4058-b42c-c8c823c1a2a1 · 2026-06-09T00:02:07.688Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

Subgoal 1/4 is the `enc` oracle equiv. The `RealOrcls` wrapper is identical on both sides, so I'll step in and inline the inner SKE `enc`, which are straight-line operator computations (no loops — `gen_CTR_encrypt_bytes` is an operator). Let me enter with `proc`.
