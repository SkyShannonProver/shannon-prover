## 🔍 Probe preview — `while (k = k0 /\ n = n0 /\ OCC.gs = gs0 /\ 1 <= i /\ c ++ gen_CTR_encrypt_bytes…` accepted · committed state unchanged
_committing this would produce (remaining 2):_
```
Current goal (remaining: 2)
Type variables: <none>
k0: key
n0: nonce
p0: message
gs0: globS
------------------------------------------------------------------------
forall (z : int),
  phoare[ z <@ OCC(I).cc(k, n, C.ofintd i); ...; i <- i + 1; :
           ((k = k0 /\
             n = n0 /\
             OCC.gs = gs0 /\
             1 <= i /\
             c ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i p =
             gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) /\
            p <> []) /\
           size p = z ==>
           (k = k0 /\
            n = n0 /\
            OCC.gs = gs0 /\
            1 <= i /\
            c ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i p =
            gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) /\
           size p < z] = 1%r
[202|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

