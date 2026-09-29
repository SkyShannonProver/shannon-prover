# Tree-0.1 · turn 4 · commit_tactic

<!-- session 32db57e0-fb2e-4cac-a35b-be9ba42eaabf · 2026-06-11T04:47:56.576Z -->

**Intent:** `commit_tactic`  
**Payload:** `by if; [wp; call E_dec_ll; auto | auto].`

---

Accepted — the suffix is the conditional `E.dec` plus assignments. Closing it with an `if` split and `E_dec_ll`.
