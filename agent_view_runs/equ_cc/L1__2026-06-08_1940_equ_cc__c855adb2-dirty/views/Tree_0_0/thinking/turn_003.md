# Tree-0.0 · turn 3 · commit_tactic

<!-- session eaf07ef5-71a1-4d41-95c4-abae017c95e5 · 2026-06-09T02:47:34.416Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (={i} /\ c{1} = c{2} /\ n{1} = n0 /\ n{2} = n0 /\ size p{1} = size p{2} /\ 1 <= i{1} /\ size c{1} + size p{1} <= max_cipher_size /\ (p{1} <> [] => size c{1} = block_size * (i{1} - 1)) /\ (forall (cc : C.counter), (n0, cc) \in ROF.m{1} => C.toint cc < i{1}) /\ (forall (nn : nonce) (cc : C.counter), (nn, cc) \in ROF.m{1} => nn \in n0 :: BNR.lenc{1}) /\ mr0 = ROin.m{1} /\ ms0 = ROout.m{1}).`

---

Loops are now aligned. Now I'll commit the `while` with my loop invariant. The key invariant pieces: synchronized `c`/`i`/sizes, the conserved `size c + size p <= max_cipher_size`, the exact `size c = block_size*(i-1)` while `p` is nonempty (gives the counter bound `i <= max_counter` at entry), and an `n0`-freshness clause `toint cc < i` that makes `(n0, ofintd i)` fresh each iteration.
