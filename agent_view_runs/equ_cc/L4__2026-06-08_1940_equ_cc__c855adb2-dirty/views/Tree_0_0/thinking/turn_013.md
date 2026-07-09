# Tree-0.0 · turn 13 · commit_tactic

<!-- session 9380bb3d-763d-4a44-bfcc-de69cee4357c · 2026-06-09T02:50:13.310Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (={c, i} /\ n{1} = n0 /\ p{2} = map (fun (_:byte) => witness<:byte>) p{1} /\ 1 <= i{1} /\ size c{1} + size p{1} <= max_cipher_size /\ (p{1} <> [] => size c{1} = (i{1} - 1) * block_size) /\ ROin.m{1} = mr0 /\ ROout.m{1} = ms0 /\ (forall (n1:nonce) (c0:C.counter), (n1, c0) \in ROF.m{1} => n1 \in n0 :: BNR.lenc{1}) /\ (forall (c0:C.counter), (n0, c0) \in ROF.m{1} => C.toint c0 < i{1})).`

---

Good — back to before the `while`, and the pre confirms `n{2} = n{1} = n0`. Let me recommit the `while` with `n{1} = n0` added to the invariant (needed for the freshness argument inside the body).
