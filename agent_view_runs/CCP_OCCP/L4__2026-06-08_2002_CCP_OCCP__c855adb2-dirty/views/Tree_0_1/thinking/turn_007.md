# Tree-0.1 · turn 7 · commit_tactic

<!-- session bc388721-b6a3-44d0-b761-d8fe1f3df5c2 · 2026-06-09T03:05:35.733Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

Now the `enc` subgoal: LHS uses `ChaCha.enc`/`Poly.mac` procedure calls (with a while loop), RHS uses the closed-form ops. I must bridge via the `chacha_spec`/`poly_spec` phoare specs. Let me step into the procedure.
