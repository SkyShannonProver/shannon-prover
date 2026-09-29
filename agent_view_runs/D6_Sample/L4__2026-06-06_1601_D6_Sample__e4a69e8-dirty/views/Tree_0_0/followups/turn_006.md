## 🔍 Probe preview — `while (={r} /\ 1 <= r{1} <= 6).` accepted · committed state unchanged
_committing this would produce (remaining 2):_
```
Current goal (remaining: 2)
Type variables: <none>
------------------------------------------------------------------------
&1 (left ) : {r : int}
&2 (right) : {i : unit, r : int}
pre = (r{1} = r{2} /\ 1 <= r{1} <= 6) /\ 5 <= r{1} /\ ! 1 <= r{2} <= 4
r <$ [1..6]                (1)  r <$ [1..6]
post = (r{1} = r{2} /\ 1 <= r{1} <= 6) /\ (5 <= r{1} <=> ! 1 <= r{2} <= 4)
[19|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

