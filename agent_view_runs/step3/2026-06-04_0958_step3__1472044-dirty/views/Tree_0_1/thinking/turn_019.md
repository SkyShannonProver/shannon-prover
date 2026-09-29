# Tree-0.1 · turn 19 · undo_to_checkpoint

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:09:05.387Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `(none)`

---

I've reached the core alignment: left does `ChaCha.enc` (ciphertext via ROF) then `Poly.mac` (tag via ROin/ROout at counter 0); right does `EncRnd.cc` then a random tag. The `ChaCha.enc ~ EncRnd.cc` step is exactly `equ_cc` — but its precondition requires `ROF.m ⊆ lenc` freshness, which my carried invariant (`inv_cpa` alone) does **not** include. `inv_cpa` only tracks `ROin.m`/`ROout.m ⊆ lenc` (needed for the tag). 

I need to strengthen the adversary-call invariant to also carry the ROF-freshness conjunct. Let me rewind to the `call` step. First inspect the checkpoint menu.
