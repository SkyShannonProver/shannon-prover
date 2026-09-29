## 🔍 Probe preview — `call (_: ={glob Log}).` accepted · committed state unchanged
_committing this would produce (remaining 2):_
```
Current goal (remaining: 2)
Type variables: <none>
------------------------------------------------------------------------
pre = arg{1} = arg{2} /\ Log.qs{1} = Log.qs{2}
    Log(LRO).o ~ Log(LRO).o
post = res{1} = res{2} /\ Log.qs{1} = Log.qs{2}
[76|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

