# Tree-0.0 · turn 8 · commit_tactic

<!-- session d09e7b01-d19a-40f9-88c6-39b890db65fb · 2026-07-09T03:52:47.156Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (i = i0 /\ 0 <= i0 < N /\ 0 <= j <= N /\ (j <= i0 => PIR.s = PIR.s') /\ (i0 < j => sxor2 PIR.s PIR.s' i0)) (N - j).`

---

`while` Form 1 fits. Let me apply it with my invariant and variant `N - j`.
