## 🔍 Probe preview — `move=> &2 r1 _ eL _; split=> [rR _|_ z1L _]; [by ring | split; [by ring | move=…` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
D : SigmaTraceDistinguisher
&m: {}
&2: {b : bool, h, a : group, w0, r, e1, z1 : ZModE.exp,
    x, x0, h0, h1 : statement, w, w1, w2 : witness, m, m0, a0 : message,
    s, r0 : secret, e, e0, e2 : challenge, z, z0 : response,
    t : message * challenge * response, sw : statement * witness,
    ms : message * secret}
r1: ZModE.exp
eL: challenge
z1L: ZModE.exp
------------------------------------------------------------------------
g ^ z1L * g ^ w0{2} ^ -eL = g ^ (z1L - eL * w0{2})
[63|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

