## 🔍 Probe preview — `auto => />.` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
forall &2 (r1 : ZModE.exp),
  r1 \in dt =>
  forall (eL : challenge),
    eL \in de =>
    (forall (rR : ZModE.exp), rR \in dt => rR = rR + eL * w0{2} - eL * w0{2}) /\
    ((forall (rR : ZModE.exp), rR \in dt => rR = rR + eL * w0{2} - eL * w0{2}) =>
     forall (z1L : ZModE.exp),
       z1L \in dt =>
       z1L = z1L - eL * w0{2} + eL * w0{2} /\
       (z1L = z1L - eL * w0{2} + eL * w0{2} =>
        g ^ z1L * g ^ w0{2} ^ -eL = g ^ (z1L - eL * w0{2})))
[62|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

