# Tree-0.1 · turn 15 · undo_to_checkpoint

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:28:34.429Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `{"checkpoint_id": "cp_1_0548457c9a125c97"}`

---

I see the checkpoint menu. There's one checkpoint:

```json
{
  "checkpoint_id": "cp_1_0548457c9a125c97",
  "label": "Rewind to before committed tactic #1",
  "committed_tactic": "proc.",
  "tactic_index": 1,
  "committed_step_index": 1,
  "restored_proof_layer": "previous_committed_state",
  "undo_scope": "recent_step",
  "why_checkpoint": "procedure entry point",


```

I'm submitting the undo request to revert the `proc.` tactic and return to the module-level goal so I can explore a different approach.
