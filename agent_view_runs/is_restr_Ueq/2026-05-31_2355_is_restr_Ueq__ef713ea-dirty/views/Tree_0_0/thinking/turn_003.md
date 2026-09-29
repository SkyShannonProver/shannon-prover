# Tree-0.0 · turn 3 · commit_tactic

<!-- session 2e75d736-140d-4a8e-9742-884a1444224e · 2026-06-01T06:56:11.261Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> h1 h2; rewrite eq_iff; split => [/fsetP heq | ->] //; apply fsetP => x; have := heq x; rewrite !in_fsetU !in_fset1; smt(nin_is_restr).`

---

The probe was accepted and shows 0 remaining goals. This tactic closes the proof completely. Let me commit it.
