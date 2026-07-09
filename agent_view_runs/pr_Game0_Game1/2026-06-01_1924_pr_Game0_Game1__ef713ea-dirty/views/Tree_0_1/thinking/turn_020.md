# Tree-0.1 · turn 20 · undo_to_checkpoint

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:53:04.733Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `{"checkpoint_id": "cp_2_678ca75386b57599"}`

---

The rewind didn't work as expected — I see updated checkpoint IDs but I'm still at the same state (after inline). The checkpoint IDs changed because new committed tactics were added. Let me try rewinding to before `proc` (cp_2).

Actually wait, looking at the checkpoint options, I need to select one. Let me rewind to before the `byequiv` — that would be cp_2 (before `proc`) or even earlier.

But looking at the list, I don't see a checkpoint for before the `byequiv` — the earliest is cp_2 (before `proc`). Wait, the byequiv was step 1. 

I see cp_2 is "Rewind to before committed tactic #2" (`proc`), and the byequiv would have been step 1. Let me try undoing to before `proc` by selecting cp_2.
