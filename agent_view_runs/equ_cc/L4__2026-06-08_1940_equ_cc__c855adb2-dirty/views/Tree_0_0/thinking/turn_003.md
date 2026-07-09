# Tree-0.0 · turn 3 · commit_tactic

<!-- session 9380bb3d-763d-4a44-bfcc-de69cee4357c · 2026-06-09T02:43:44.266Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (={c, i} /\ p{2} = map (fun (_:byte) => witness<:byte>) p{1} /\ 1 <= i{1} /\ size c{1} + size p{1} <= max_cipher_size /\ (p{1} <> [] => size c{1} = (i{1} - 1) * block_size) /\ ROin.m{1} = mr0 /\ ROout.m{1} = ms0 /\ (forall (n1:nonce) (c0:C.counter), (n1, c0) \in ROF.m{1} => n1 \in n0 :: BNR.lenc{1}) /\ (forall (c0:C.counter), (n0, c0) \in ROF.m{1} => C.toint c0 < i{1})).`

---

Both loops are now aligned. Now I'll set up the relational `while` with an invariant. My reasoning for the invariant:

- `={c, i}` — outputs and counter stay synced
- `p{2} = map witness p{1}` — right's message is the size-preserving witness-map of left's (preserved by `drop`, keeps guards in sync)
- `size c{1} + size p{1} <= max_cipher_size` — gives the `size c{1} <= max_cipher_size` post at exit
- `p{1} <> [] => size c{1} = (i{1}-1)*block_size` — at a call all prior chunks were full blocks, so this bounds `i <= max_counter` ⟹ `toint(ofintd i) = i`
- `ROin.m = mr0 /\ ROout.m = ms0` — loop only touches ROF (counter ≠ 0)
- ROF membership ⟹ nonce ∈ n0::lenc (the post)
- `(n0,c0) ∈ ROF.m => toint c0 < i` — gives freshness of `(n0, ofintd i)` at each call
