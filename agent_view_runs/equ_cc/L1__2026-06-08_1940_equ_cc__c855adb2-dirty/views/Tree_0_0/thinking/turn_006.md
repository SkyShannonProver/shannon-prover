# Tree-0.0 · turn 6 · commit_tactic

<!-- session eaf07ef5-71a1-4d41-95c4-abae017c95e5 · 2026-06-09T02:49:56.342Z -->

**Intent:** `commit_tactic`  
**Payload:** `auto; smt(C.ofintdK gt0_block_size max_cipher_size_ok C.gt0_max_counter size_eq0 size_ge0).`

---

Now I'll discharge this side goal: `auto` processes the assignments, then `smt` proves `toint(ofintd i) ≠ 0` using the round-trip lemma plus the `i ≤ max_counter` bound derived from the size invariant.
