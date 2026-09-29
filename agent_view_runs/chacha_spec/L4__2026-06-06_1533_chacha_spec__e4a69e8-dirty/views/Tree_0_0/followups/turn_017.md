## 🔍 Probe preview — `move=> &hr [[[eqk eqn eqgs Hrest] Hne] Hsz].` accepted · committed state unchanged
_committing this would produce (remaining 2):_
```
Current goal (remaining: 2)
Type variables: <none>
k0: key
n0: nonce
p0: message
gs0: globS
sz: int
&hr: {i : int, c : byte list, k, k0 : key, n, n0 : nonce, c0 : C.counter,
     z : block, p : message}
eqk: k{hr} = k0
eqn: n{hr} = n0 /\
     OCC.gs{hr} = gs0 /\
     1 <= i{hr} /\
     c{hr} ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i{hr} p{hr} =
     gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0
eqgs: p{hr} <> []
Hrest: size p{hr} = sz
Hne: message := drop block_size p{hr}
Hsz: int := i{hr} + 1
------------------------------------------------------------------------
(k{hr} = k0 /\
 n{hr} = n0 /\
 OCC.gs{hr} = gs0 /\
 1 <= Hsz /\
 c{hr} ++
 take (size p{hr})
   (bytes_of_block
      (extend p{hr} +^ cc OCC.gs{hr} k{hr} n{hr} (C.ofintd i{hr}))) ++
 gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 Hsz Hne =
 gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) /\
size Hne < sz
[204|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

