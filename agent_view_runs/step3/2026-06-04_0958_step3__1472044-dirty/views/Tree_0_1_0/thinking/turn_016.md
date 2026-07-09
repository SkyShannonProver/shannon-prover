# Tree-0.1.0 · turn 16 · undo_to_checkpoint

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:33:54.774Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `{"checkpoint_id": "cp_11_ac02842fbedfaed4"}`

---

The checkpoint menu wasn't in the bounded result. Let me read the manager result file to find the available rewind points.

The checkpoint menu rendered ephemerally and isn't in these files. Let me check the full workspace view JSON for the menu's submit objects.

Found the menu. The key obstacle is confirmed by the manager's own `gap_analysis`: *"Map update key head and membership/list head are both visible, but no equality path between them is visible"* — exactly the `p{1}.\`1` vs `p{2}.\`1` gap, and it points to checkpoint `cp_11` (before the seq cut) as the repair. The `seq` cut assertion `Q` is too weak. I'll rewind to before the seq cut (`cp_11_ac02842fbedfaed4`) and re-issue it with the extra conjunct `p{1} = p{2}`.
