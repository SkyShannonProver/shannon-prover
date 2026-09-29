# Tree-0.1 · turn 47 · undo_to_checkpoint

<!-- session 214c307b-d923-4d2c-a74c-72e428a28c22 · 2026-06-04T16:46:29.985Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `(none)`

---

I found a gap: my intermediate relation `R` (from the `seq`) dropped the fact `n{1} = p{1}.\`1`, which the final invariant needs (the new RO key is `(n,0)` and `lenc` grows by `p.\`1`). I need to strengthen `R`. Let me rewind to the `seq`.
