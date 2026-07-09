# Tree-0.0 · turn 8 · commit_tactic

<!-- session 420ddf0e-a769-49f3-83cb-e3b3c3d9112b · 2026-06-03T16:04:46.401Z -->

**Intent:** `commit_tactic`  
**Payload:** `auto; call (_: true); auto.`

---

`rnd predT` is a bd_hoare form — this is a plain `hoare[c1 : true ==> true]` goal (post is `true`), so it needs plain forms. Let me use `auto` which chains wp/rnd, then handle the adversary call with a trivial invariant.
