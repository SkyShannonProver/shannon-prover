## 🔍 Probe preview — `rewrite kK ih; split=> //; rewrite xorbC xorbA xorbK xorbC xorb0.` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
P: block -> block -> block
Pi: block -> block -> block
k: block
kK: cancel (P k) (Pi k)
pi: block
p: block list
ih: forall (st : block), cbc_dec Pi k st (cbc_enc P k st p) = p
st: block
------------------------------------------------------------------------
pi = pi
[133|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

