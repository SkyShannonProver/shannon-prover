# Tree-0.0 · turn 13 · undo_to_checkpoint

<!-- session 420ddf0e-a769-49f3-83cb-e3b3c3d9112b · 2026-06-03T16:10:49.185Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `{"checkpoint_id": "cp_7_c5822fcae3bff6ca"}`

---

The empty-payload call should surface a checkpoint menu. Let me read the refreshed view for it.

Found it — `cp_7` is "Before seq cut #7" (the seq-13 cut). Undoing there returns me to `phoare[1-21 : true ==> post] <= bound`, where I'll redo the cut with `G1.w <> zero` carried.
