## 🔍 Probe preview — `proc.` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
------------------------------------------------------------------------
Context : hr: {pk : PKE_.pkey, sk : PKE_.skey, m : PKE_.plaintext,
              c : PKE_.ciphertext, m' : PKE_.plaintext option}
pre = true
(1)  (pk, sk) <@ CramerShoup.kg()
(2)  c <@ CramerShoup.enc(pk, m)
(3)  m' <@ CramerShoup.dec(sk, c)
post = m' = Some m
[51|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

