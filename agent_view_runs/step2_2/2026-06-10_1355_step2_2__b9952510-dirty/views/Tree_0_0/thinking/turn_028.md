# Tree-0.0 · turn 28 · commit_tactic

<!-- session e13e9012-11a0-44c0-9ba5-a5d298cc9a0b · 2026-06-10T21:21:14.379Z -->

**Intent:** `commit_tactic`  
**Payload:** `have Hcrux : forall (c : ciphertext), c \in Mem.lc{hr} => dec RO.m{hr} Mem.k{hr} c <> None<:nonce * associated_data * bytes> => c.`1 \in take (i{hr} + 1) ns{hr} => forged{hr} || test_poly (nth witness<:nonce> ns{hr} i{hr}) Mem.lc{hr} (mk_rs (oget RO.m{hr}.[nth witness<:nonce> ns{hr} i{hr}, C.ofintd 0])).`1 (mk_rs (oget RO.m{hr}.[nth witness<:nonce> ns{hr} i{hr}, C.ofintd 0])).`2.`

---

Clean logical goal. The crux conjunct is the `forall c` clause. Let me state it as a `have` so I can prove it in isolation, then close the rest automatically.
