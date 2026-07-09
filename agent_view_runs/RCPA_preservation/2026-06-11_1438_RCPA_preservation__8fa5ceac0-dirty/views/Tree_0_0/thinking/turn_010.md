# Tree-0.0 · turn 10 · commit_tactic

<!-- session 18dbf0b7-3604-4e21-875b-a18c9ed05753 · 2026-06-11T21:42:11.158Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp; rnd; wp; call{2} Mtag_ll; auto.`

---

`call{2}` hit a trailing assignment — need another `wp` after `rnd` to expose the `M.tag` call.
