## 🔍 Probe preview — `while{2} (0 <= i{2} <= size ns{2}) (size ns{2} - i{2}).` accepted · committed state unchanged
_committing this would produce (remaining 4):_
```
Current goal (remaining: 4)
Type variables: <none>
&m: {}
------------------------------------------------------------------------
forall _ (z : int),
  phoare[ n <- nth witness<:nonce> ns i; ...; i <- i + 1; :
           (0 <= i <= size ns /\ i < size ns) /\ size ns - i = z ==>
           0 <= i <= size ns /\ size ns - i < z] = 1%r
[315|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

