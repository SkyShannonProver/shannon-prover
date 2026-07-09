# Tree-0.1 · turn 27 · probe_tactic

<!-- session 794a61bb-7f1e-4330-b53e-4ab039bb259a · 2026-06-04T08:51:24.754Z -->

**Intent:** `probe_tactic`  
**Payload:** `have Hll : forall (x : nonce * C.counter), is_lossless dblock by move=> ?; exact Block.dblock_ll.`

---

The `_` binder name is invalid in a `have` formula. Using a named binder:
