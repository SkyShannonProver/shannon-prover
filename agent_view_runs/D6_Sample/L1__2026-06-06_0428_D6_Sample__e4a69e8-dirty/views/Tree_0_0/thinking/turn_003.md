# Tree-0.0 · turn 3 · commit_tactic

<!-- session b3244a16-2444-4a7a-bcc6-185a4960b204 · 2026-06-06T11:29:54.670Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (={r} /\ 1 <= r{1} <= 6).`

---

Both sides are now bare while loops with `r{1}=r{2}=5`. Now apply the relational `while` rule with invariant `={r} /\ 1 <= r{1} <= 6`.
