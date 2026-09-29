# Tree-0.1 · turn 26 · probe_tactic

<!-- session 794a61bb-7f1e-4330-b53e-4ab039bb259a · 2026-06-04T08:51:18.971Z -->

**Intent:** `probe_tactic`  
**Payload:** `have Hll : forall (_ : nonce * C.counter), is_lossless dblock by move=> ?; exact Block.dblock_ll.`

---

The inline hypothesis lambda caused a parse error. Let me introduce the losslessness fact as a named hypothesis first, then use it.
