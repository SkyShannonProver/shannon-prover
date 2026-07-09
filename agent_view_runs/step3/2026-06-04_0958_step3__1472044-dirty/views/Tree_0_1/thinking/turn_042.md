# Tree-0.1 · turn 42 · undo_last_step

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:35:53.043Z -->

**Intent:** `undo_last_step`  
**Payload:** `(none)`

---

**Accepted!** So procedure matching was never the problem — the issue is the `n0` argument: a closed term (`witness`) works, but a memory-indexed expression (`n{1}`, `p{1}.\`1`) or an evar (`_`) does not. I need `n0` as a **logical variable** too. Let me undo this wrong-`n0` call and generalize the nonce as well.
