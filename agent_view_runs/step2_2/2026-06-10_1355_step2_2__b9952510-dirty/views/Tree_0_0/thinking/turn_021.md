# Tree-0.0 · turn 21 · commit_tactic

<!-- session e13e9012-11a0-44c0-9ba5-a5d298cc9a0b · 2026-06-10T21:16:33.861Z -->

**Intent:** `commit_tactic`  
**Payload:** `while{2} (0 <= i{2} <= size ns{2} /\ ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}) /\ Mem.lc{1} = Mem.lc{2} /\ RO.m{1} = RO.m{2} /\ Mem.k{1} = Mem.k{2} /\ (forall (c : ciphertext), (c \in Mem.lc{2}) => dec RO.m{2} Mem.k{2} c <> None => (c.`1 \in take i{2} ns{2}) => forged{2})) (size ns{2} - i{2}).`

---

Now the one-sided loop. I'll apply `while{2}` with a relational invariant: `forged` holds for any forging ciphertext whose nonce has already been processed (`c.'1 ∈ take i ns`), carrying the side-equalities and `ns = undup(...)`.
