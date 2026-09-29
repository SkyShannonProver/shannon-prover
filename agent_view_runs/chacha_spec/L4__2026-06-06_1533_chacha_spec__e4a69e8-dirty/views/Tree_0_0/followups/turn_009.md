## 🔍 Probe preview — `move=> sz; inline OCC(I).cc.` accepted · committed state unchanged
_committing this would produce (remaining 2):_
```
Current goal (remaining: 2)
Type variables: <none>
k0: key
n0: nonce
p0: message
gs0: globS
sz: int
------------------------------------------------------------------------
Context : hr: {i : int, c : byte list, k, k0 : key, n, n0 : nonce,
              c0 : C.counter, z : block, p : message}
Bound   : [=] 1%r
pre =
  ((k = k0 /\
    n = n0 /\
    OCC.gs = gs0 /\
    1 <= i /\
    c ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i p =
    gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) /\
   p <> []) /\
  size p = sz
(1)  k0 <- k
(2)  n0 <- n
(3)  c0 <- C.ofintd i
(4)  z <- cc OCC.gs k0{!hr} n0{!hr} c0
(5)  c <- c ++ take (size p) (bytes_of_block (extend p +^ z))
(6)  p <- drop block_size p
(7)  i <- i + 1
post =
  (k = k0 /\
   n = n0 /\
   OCC.gs = gs0 /\
   1 <= i /\
   c ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i p =
   gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) /\
  size p < sz
[203|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

