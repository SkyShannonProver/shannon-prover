## 🔍 Probe preview — `rcondt{1} 25.` accepted · committed state unchanged
_committing this would produce (remaining 2):_
```
Current goal (remaining: 2)
Type variables: <none>
D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
forall &m0,
  hoare[ w0 <$ $dt; ...; v <- v1 = v'; : (glob D) = (glob D){m0} ==> v ]
[48|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

