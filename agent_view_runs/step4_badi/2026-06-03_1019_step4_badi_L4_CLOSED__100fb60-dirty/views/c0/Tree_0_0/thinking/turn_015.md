# Tree-0.0 · turn 15 · undo_to_checkpoint

<!-- session 7d6b85e1-efc5-4558-ab30-99a9e554877b · 2026-06-03T17:30:55.570Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `(none)`

---

I made an error: my invariant included `glob Mem` (which contains `Mem.k`), but `Mem.k` is never set (no `kg` call) and my `byequiv` precondition only equates `glob A` — so `Mem.k{1}=Mem.k{2}` is unprovable and unneeded (oracles don't use the key). I need to rewind and replace `glob Mem` with just `Mem.lc, Mem.log`. Let me get the checkpoint menu.
