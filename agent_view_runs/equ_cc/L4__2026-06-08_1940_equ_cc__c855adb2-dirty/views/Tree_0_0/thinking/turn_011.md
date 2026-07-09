# Tree-0.0 · turn 11 · undo_to_checkpoint

<!-- session 9380bb3d-763d-4a44-bfcc-de69cee4357c · 2026-06-09T02:49:47.344Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `{"checkpoint_id": "cp_4_92843bd13814cb9f"}`

---

The only checkpoint offered rewinds to before the `inline` (step 4), but I need to redo the `while` (step 3) itself. Let me rewind to before the inline first, which gives a clean post-`while` body goal, then undo the `while` from there.
