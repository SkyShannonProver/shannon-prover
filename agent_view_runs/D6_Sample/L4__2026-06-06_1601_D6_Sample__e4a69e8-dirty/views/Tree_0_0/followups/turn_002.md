## 🔍 Probe preview — `proc.` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
------------------------------------------------------------------------
&1 (left ) : {r : int}
&2 (right) : {i : unit, r : int}
pre = (i{2}, r{2}).`2 = 5
r <- 5                     (1--)  while (! 1 <= r <= 4) {
                           (1.1)    r <$ [1..6]
                           (1--)  }
while (5 <= r) {           (2--)
  r <$ [1..6]              (2.1)
}                          (2--)
post = r{1} = r{2}
[17|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

