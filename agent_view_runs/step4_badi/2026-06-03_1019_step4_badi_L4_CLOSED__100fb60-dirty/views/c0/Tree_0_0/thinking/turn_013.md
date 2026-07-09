# Tree-0.0 · turn 13 · commit_tactic

<!-- session 7d6b85e1-efc5-4558-ab30-99a9e554877b · 2026-06-03T17:30:01.045Z -->

**Intent:** `commit_tactic`  
**Payload:** `auto; smt().`

---

The `auto` probe is flagged as closing. Let me verify it fully closes goal 1.

`auto` reduces it to a pure arithmetic residual (`0 = b2i(nth0 < size [])` etc.), closable with `smt` using `H`. Let me commit the combined tactic.
