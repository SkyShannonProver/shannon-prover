## 🔍 Probe preview — `byequiv (_: ={glob A} ==> (exists (c:ciphertext), c \in Mem.lc /\ dec StLSke.gs…` accepted · committed state unchanged
_committing this would produce (remaining 3):_
```
Current goal (remaining: 3)
Type variables: <none>
&m: {}
------------------------------------------------------------------------
pre = (glob A){1} = (glob A){2}
    UFCMA(A, St).main ~ UFCMA_poly(A, FinRO).main
post =
  (exists (c : ciphertext),
     (c \in Mem.lc{1}) /\
     dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes>) =>
  res{2}
[308|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

