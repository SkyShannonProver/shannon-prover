## 🔍 Probe preview — `move=> &hr H; split; first by smt(dbool_ll); move=> _ v hv; rewrite /predT /=; …` accepted · committed state unchanged
_committing this would produce (remaining 2):_
```
Current goal (remaining: 2)
Type variables: <none>
&m: {}
i0: int
hi0: 0 <= i0 < N
z: int
&hr: {b : bool, i, j : int, s, s0 : int list, r, r' : word}
H: (((0 <= j{hr} <= N /\
      i{hr} = i0 /\
      big predT<:int> a PIR.s{hr} +^ big predT<:int> a PIR.s'{hr} =
      if i0 < j{hr} then a i0 else zerow) /\
     j{hr} < N) /\
    N - j{hr} = z) /\
   true
------------------------------------------------------------------------
weight {0,1} = 1%r =>
forall (v : bool),
  v \in {0,1} =>
  predT v <=>
  if j{hr} = i{hr} then
    if v then
      let j0 = j{hr} + 1 in
      (0 <= j0 <= N /\
       i{hr} = i0 /\
       big predT<:int> a (j{hr} :: PIR.s{hr}) +^ big predT<:int> a PIR.s'{hr} =
       if i0 < j0 then a i0 else zerow) /\
      N - j0 < z
    else
      let j0 = j{hr} + 1 in
      (0 <= j0 <= N /\
       i{hr} = i0 /\
       big predT<:int> a PIR.s{hr} +^ big predT<:int> a (j{hr} :: PIR.s'{hr}) =
       if i0 < j0 then a i0 else zerow) /\
      N - j0 < z
  else
    if v then
      let j0 = j{hr} + 1 in
      (0 <= j0 <= N /\
       i{hr} = i0 /\
       big predT<:int> a (j{hr} :: PIR.s{hr}) +^
       big predT<:int> a (j{hr} :: PIR.s'{hr}) =
       if i0 < j0 then a i0 else zerow) /\
      N - j0 < z
    else
      let j0 = j{hr} + 1 in
      (0 <= j0 <= N /\
       i{hr} = i0 /\
       big predT<:int> a PIR.s{hr} +^ big predT<:int> a PIR.s'{hr} =
       if i0 < j0 then a i0 else zerow) /\
      N - j0 < z
[25|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

