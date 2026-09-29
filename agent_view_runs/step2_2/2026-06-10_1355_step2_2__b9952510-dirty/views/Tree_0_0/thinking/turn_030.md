# Tree-0.0 · turn 30 · commit_tactic

<!-- session e13e9012-11a0-44c0-9ba5-a5d298cc9a0b · 2026-06-10T21:22:05.462Z -->

**Intent:** `commit_tactic`  
**Payload:** `have heq : take (i{hr} + 1) ns{hr} = rcons (take i{hr} ns{hr}) (nth witness<:nonce> ns{hr} i{hr}) by apply (take_nth witness<:nonce>); smt().`

---

Let me establish the `take (i+1)` split as an equation.
