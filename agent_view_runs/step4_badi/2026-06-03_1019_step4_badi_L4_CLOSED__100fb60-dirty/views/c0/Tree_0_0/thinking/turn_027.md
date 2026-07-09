# Tree-0.0 · turn 27 · commit_tactic

<!-- session 7d6b85e1-efc5-4558-ab30-99a9e554877b · 2026-06-03T17:41:53.977Z -->

**Intent:** `commit_tactic`  
**Payload:** `sp 1 1.`

---

The then-branch differs only in the inner `O.enc` call (which differs only in `set_bad1`); the `BNR.lenc` update and guard are identical. Let me absorb the leading `c <- witness` with `sp`, then handle the `if`.
