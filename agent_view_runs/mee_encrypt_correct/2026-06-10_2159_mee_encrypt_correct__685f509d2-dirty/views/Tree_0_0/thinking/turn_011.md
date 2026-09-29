# Tree-0.0 · turn 11 · commit_tactic

<!-- session f6525898-083c-4c36-8d4f-388aae59ebc6 · 2026-06-11T05:08:02.134Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (0 <= i <= size p' /\ ek = _ek /\ size c = i + 1 /\ c = head witness c :: cbc_enc AES _ek (head witness c) (take i p') /\ s = nth witness c i /\ head witness c :: cbc_enc AES _ek (head witness c) p' = _c).`

---

Now the hoare correctness of the loop. Committing the `while` invariant that tracks `c` as the CBC prefix computation.
