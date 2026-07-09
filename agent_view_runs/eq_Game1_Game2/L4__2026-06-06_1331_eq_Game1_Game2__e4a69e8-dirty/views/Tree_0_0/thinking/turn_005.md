# Tree-0.0 · turn 5 · probe_tactic

<!-- session b5726082-8cc7-4cb4-b705-be1b5ea6c6f3 · 2026-06-06T20:32:58.026Z -->

**Intent:** `probe_tactic`  
**Payload:** `call (_: ={glob Log, glob LRO}).`

---

`call (_: ={glob Log})` only couples `Log.qs`, but the oracle body calls `LRO.o`, whose map must also be coupled for `res` to be equal. Let me probe with the RO state included.
