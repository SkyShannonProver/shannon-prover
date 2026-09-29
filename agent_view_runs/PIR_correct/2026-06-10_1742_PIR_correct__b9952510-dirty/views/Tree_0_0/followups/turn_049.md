## 🔍 Probe preview — `skip.` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
&m: {}
i0: int
hi0: 0 <= i0 < N
------------------------------------------------------------------------
forall &hr,
  j{hr} = 0 /\ PIR.s'{hr} = [] /\ PIR.s{hr} = [] /\ i{hr} = i0 =>
  (0 <= j{hr} <= N /\
   i{hr} = i0 /\
   big predT<:int> a PIR.s{hr} +^ big predT<:int> a PIR.s'{hr} =
   if i0 < j{hr} then a i0 else zerow) /\
  forall (s1 s' : int list) (j0 : int),
    ((0 <= j0 <= N /\
      i{hr} = i0 /\
      big predT<:int> a s1 +^ big predT<:int> a s' =
      if i0 < j0 then a i0 else zerow) =>
     N - j0 <= 0 => ! j0 < N) /\
    (! j0 < N =>
     (0 <= j0 <= N /\
      i{hr} = i0 /\
      big predT<:int> a s1 +^ big predT<:int> a s' =
      if i0 < j0 then a i0 else zerow) =>
     big predT<:int> a s1 +^ big predT<:int> a s' = a i0)
[36|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

