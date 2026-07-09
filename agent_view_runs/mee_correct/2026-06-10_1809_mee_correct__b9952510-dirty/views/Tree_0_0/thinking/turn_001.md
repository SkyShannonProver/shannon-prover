# Tree-0.0 · turn 1 · commit_tactic

<!-- session d678cb3d-ec3a-4839-8f56-f54a60203158 · 2026-06-11T01:10:14.732Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> PiK; rewrite /mee_enc /mee_dec /= cbc_correct // padK /=.`

---

I'll start by reading the current workspace view to understand the proof state.

Let me read the followup and the source file to understand the lemma and its context.

This is MAC-then-Pad-then-CBC functional correctness. The proof structure is clear:
- `mee_enc` = `cbc_enc P ek iv (pad m (M mk m))`
- `mee_dec` decrypts via `cbc_dec`, then `unpad`, then checks the MAC
- `cbc_correct` (line 244) gives `cbc_dec Pi ek iv (cbc_enc ...) = pad m (M mk m)` under `cancel (P ek) (Pi ek)`
- `padK` (line 330) gives `unpad (pad m t) = Some (m,t)`, and the MAC check `M mk m = M mk m` is trivially true.

Let me commit the combined tactic.
