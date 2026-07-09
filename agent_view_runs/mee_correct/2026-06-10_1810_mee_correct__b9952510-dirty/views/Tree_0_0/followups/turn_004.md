## 🔍 Probe preview — `rewrite (cbc_correct P Pi ek iv (pad m (M mk m)) hPi) padK /=.` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
P: block -> block -> block
Pi: block -> block -> block
M: mK -> msg -> tag
ek: block
mk: mK
iv: block
m: msg
hPi: cancel (P ek) (Pi ek)
------------------------------------------------------------------------
true
[196|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

