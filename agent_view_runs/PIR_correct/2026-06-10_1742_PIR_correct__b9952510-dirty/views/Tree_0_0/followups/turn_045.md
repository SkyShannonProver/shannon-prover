## 🔍 Probe preview — `rewrite /predT in H; smt(BBS.big_cons xorwA xorwC xorw0 xorwK).` accepted · committed state unchanged
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
v: bool
hv: v \in {0,1}
hji: j{hr} <> i{hr}
------------------------------------------------------------------------
if v then
  (0 <= j{hr} + 1 <= N /\
   i{hr} = i0 /\
   big (fun (_ : int) => true) a (j{hr} :: PIR.s{hr}) +^
   big (fun (_ : int) => true) a (j{hr} :: PIR.s'{hr}) =
   if i0 < j{hr} + 1 then a i0 else zerow) /\
  N - (j{hr} + 1) < z
else
  (0 <= j{hr} + 1 <= N /\
   i{hr} = i0 /\
   big (fun (_ : int) => true) a PIR.s{hr} +^
   big (fun (_ : int) => true) a PIR.s'{hr} =
   if i0 < j{hr} + 1 then a i0 else zerow) /\
  N - (j{hr} + 1) < z
[34|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

