# Tree-0.1 · turn 18 · probe_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:41:49.627Z -->

**Intent:** `probe_tactic`  
**Payload:** `while (0 <= i /\ i <= size c /\ padded = cbc_dec AESi ek (head witness _c) (take i c) /\ s = last (head witness _c) (take i c) /\ p = None /\ ek = _ek /\ mk = _mk /\ c = behead _c) (size c - i).`

---

Now I have 4 remaining goals. The current goal is the REAL while loop proof — phoare with `Bound = [=] 1%r`:
- pre: the existential with initial conditions
- program: the while loop
- post: `padded = cbc_dec AESi _ek (head witness _c) (behead _c) /\ mk = _mk /\ p = None`

This is the key goal — showing the while loop actually computes `cbc_dec`. Now I can apply `while (INV) (VAR)` since this is phoare and the while loop IS the last statement.
I need to establish the loop invariant that tracks the decryption progress: the padded value equals the CBC decryption of the ciphertext processed so far, the state tracks the last block, and the other variables remain unchanged. The variant is the remaining ciphertext size. Once the loop terminates when we've processed all blocks, the padded value will equal the full CBC decryption as required.
