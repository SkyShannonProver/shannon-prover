# Tree-0.0 · turn 2 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T16:56:01.696Z -->

**Intent:** `commit_tactic`  
**Payload:** `auto; smt().`

---

`hoare` reduced it to a hoare judgment with negated post. Now the post is `!(... larger conjunction ...)` and the pre is `!(... subset of that conjunction ...)`. Since the samples `r'`/`r` don't change any of the relevant variables, and the post's conjunction is a superset of the pre's, the negation follows directly. Let me discharge with `auto; smt()`.
