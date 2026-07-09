# Tree-0.0 · turn 3 · commit_tactic

<!-- session f272040b-88fb-4cdc-a222-8ca173fe3cdf · 2026-06-11T04:58:17.265Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (0 <= i <= size c /\ ek = _ek /\ mk = _mk /\ c = behead _c /\ s = nth witness (head witness _c :: c) i /\ padded = cbc_dec AESi _ek (head witness _c) (take i c)) (size c - i).`

---

Loop is now last. Submitting the `while` with invariant and variant.
