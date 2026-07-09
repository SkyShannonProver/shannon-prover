## 🔍 Probe preview — `move=> s; rewrite /take_xor /= take0.` accepted · committed state unchanged
_committing this would produce (remaining 3):_
```
Current goal (remaining: 3)
Type variables: <none>
k0: key
n0: nonce
p0: message
gs0: globS
sz: int
&hr: {i : int, c : byte list, k, k0 : key, n, n0 : nonce, c0 : C.counter,
     z : block, p : message}
Hne: p{hr} <> []
Hsz: size p{hr} = sz
eqk: k{hr} = k0
eqn: n{hr} = n0
eqgs: OCC.gs{hr} = gs0
ge1i: 1 <= i{hr}
Heq: c{hr} ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i{hr} p{hr} =
     gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0
s: block
------------------------------------------------------------------------
[] = []
[207|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

