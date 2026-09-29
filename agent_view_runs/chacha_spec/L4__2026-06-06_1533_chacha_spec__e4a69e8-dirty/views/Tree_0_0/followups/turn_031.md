## 🔍 Probe preview — `split; first by smt(). rewrite -Heq (gen_CTR_encrypt_bytes_cons take_xor (cc gs…` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
k0: key
n0: nonce
p0: message
gs0: globS
------------------------------------------------------------------------
Context : hr: {i : int, c : byte list, k : key, n : nonce, z : block,
              p : message}
Bound   : [=] 1%r
pre =
  (k, n, p).`1 = k0 /\ (k, n, p).`2 = n0 /\ (k, n, p).`3 = p0 /\ OCC.gs = gs0
(1)  c <- []
(2)  i <- 1
post =
  (k = k0 /\
   n = n0 /\
   OCC.gs = gs0 /\
   1 <= i /\
   c ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i p =
   gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) /\
  forall (c0 : byte list) (i0 : int) (p1 : message),
    (k = k0 /\
     n = n0 /\
     OCC.gs = gs0 /\
     1 <= i0 /\
     c0 ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i0 p1 =
     gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0 =>
     size p1 <= 0 => p1 = []) /\
    (p1 = [] =>
     k = k0 /\
     n = n0 /\
     OCC.gs = gs0 /\
     1 <= i0 /\
     c0 ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i0 p1 =
     gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0 =>
     c0 = gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0)
[210|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

