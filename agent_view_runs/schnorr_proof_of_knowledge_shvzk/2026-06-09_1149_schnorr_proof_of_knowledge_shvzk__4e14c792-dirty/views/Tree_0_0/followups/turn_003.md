## 🔍 Probe preview — `byequiv => //.` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
pre = (glob D){2} = (glob D){m} /\ (glob D){1} = (glob D){m}
    SimulateHonestVerifier(SchnorrPK, SchnorrPKAlgorithms, D).gameIdeal ~
SimulateHonestVerifier(SchnorrPK, SchnorrPKAlgorithms, D).gameReal
post = res{1} = res{2}
[41|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

