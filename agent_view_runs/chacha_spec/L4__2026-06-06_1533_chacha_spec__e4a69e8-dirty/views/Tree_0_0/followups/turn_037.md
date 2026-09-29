## 🔍 Probe preview — `move=> &hr /= [eqk [eqn [eqp eqgs]]].` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
k0: key
n0: nonce
p0: message
gs0: globS
Hnil: forall (s : block), take_xor [] s = []
&hr: {i : int, c : byte list, k : key, n : nonce, z : block, p : message}
eqk: k{hr} = k0
eqn: n{hr} = n0
eqp: p{hr} = p0
eqgs: OCC.gs{hr} = gs0
------------------------------------------------------------------------
(k{hr} = k0 /\
 n{hr} = n0 /\
 OCC.gs{hr} = gs0 /\
 gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p{hr} =
 gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) /\
forall (c0 : byte list) (i0 : int) (p1 : message),
  (k{hr} = k0 /\
   n{hr} = n0 /\
   OCC.gs{hr} = gs0 /\
   1 <= i0 /\
   c0 ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i0 p1 =
   gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0 =>
   size p1 <= 0 => p1 = []) /\
  (p1 = [] =>
   k{hr} = k0 /\
   n{hr} = n0 /\
   OCC.gs{hr} = gs0 /\
   1 <= i0 /\
   c0 ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i0 p1 =
   gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0 =>
   c0 = gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0)
[214|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

