## 🔍 Probe preview — `rewrite (cbc_correct P Pi ek iv (pad m (M mk m)) hPi).` accepted · committed state unchanged
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
(if unpad (pad m (M mk m)) <> None<:octet list * tag> then
   let (m0, t) = oget (unpad (pad m (M mk m))) in
   if M mk m0 = t then Some m0 else None<:octet list>
 else None<:octet list>) =
Some m
[196|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

