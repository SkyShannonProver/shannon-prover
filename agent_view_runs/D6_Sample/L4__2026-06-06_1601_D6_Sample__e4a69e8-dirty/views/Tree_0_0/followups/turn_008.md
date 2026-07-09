## 🔍 Probe preview — `auto=> />; smt(supp_dinter).` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
------------------------------------------------------------------------
&1 (left ) : {r : int}
&2 (right) : {i : unit, r : int}
pre = r{1} = 5 /\ (i{2}, r{2}).`2 = 5
post =
  ((r{1} = r{2} /\ 1 <= r{1} <= 6) /\ (5 <= r{1} <=> ! 1 <= r{2} <= 4)) /\
  forall (r_L r_R : int),
    ! 5 <= r_L => 1 <= r_R <= 4 => r_L = r_R /\ 1 <= r_L <= 6 => r_L = r_R
[20|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

