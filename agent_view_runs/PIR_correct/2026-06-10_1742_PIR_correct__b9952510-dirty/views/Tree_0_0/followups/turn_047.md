## 🔍 Probe preview — `rewrite /predT in H; smt(BBS.big_cons xorwA xorwC xorw0 xorwK).` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
&m: {}
i0: int
hi0: 0 <= i0 < N
------------------------------------------------------------------------
Context : hr: {b : bool, i, j : int, s, s0 : int list, r, r' : word}
Bound   : [=] 1%r
pre = j = 0 /\ PIR.s' = [] /\ PIR.s = [] /\ i = i0
post =
  (0 <= j <= N /\
   i = i0 /\
   big predT<:int> a PIR.s +^ big predT<:int> a PIR.s' =
   if i0 < j then a i0 else zerow) /\
  forall (s1 s' : int list) (j0 : int),
    ((0 <= j0 <= N /\
      i = i0 /\
      big predT<:int> a s1 +^ big predT<:int> a s' =
      if i0 < j0 then a i0 else zerow) =>
     N - j0 <= 0 => ! j0 < N) /\
    (! j0 < N =>
     (0 <= j0 <= N /\
      i = i0 /\
      big predT<:int> a s1 +^ big predT<:int> a s' =
      if i0 < j0 then a i0 else zerow) =>
     big predT<:int> a s1 +^ big predT<:int> a s' = a i0)
[35|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

