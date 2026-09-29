# Tree-0.0 · turn 9 · undo_to_checkpoint

<!-- session 9380bb3d-763d-4a44-bfcc-de69cee4357c · 2026-06-09T02:48:58.122Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `(none)`

---

I spotted a gap in my `while` invariant: the freshness of `x1 = (n{1}, ofintd i)` in ROF.m requires knowing `n{1} = n0`, but I never carried that into the invariant (the loop body only sees the invariant, not the outer pre). I need to add `n{1} = n0`. Let me rewind to before the `while`.
