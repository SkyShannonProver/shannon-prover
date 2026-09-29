# Tree-0.1 · turn 15 · probe_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:40:59.231Z -->

**Intent:** `probe_tactic`  
**Payload:** `wp; call (_: true); auto.`

---

Now I need to close the loop body: `pre = i < size c`, `post = true`, with the body containing a call to `PRPc.PseudoRP.fi`. Since `post = true`, I just need to handle the call. Let me try `wp; call (_: true); wp; skip; auto.` or similar.

Actually, the call is in the middle of the body. Let me try:
1. `wp.` — push backwards past the assignments after the call (lines 3-5)
2. `call (_: true).` — handle the call with trivial spec
3. `wp; skip.` or `auto.` — handle the remaining assignments and close
Let me test chaining these tactics together with `wp; call (_: true); auto.` to see if that closes the proof cleanly.
