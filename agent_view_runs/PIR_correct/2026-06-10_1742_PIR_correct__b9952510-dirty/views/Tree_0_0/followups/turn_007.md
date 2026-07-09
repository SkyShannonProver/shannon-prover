## 🔍 Probe preview — `while (0 <= j <= N /\ i = i0 /\ big predT a PIR.s +^ big predT a PIR.s' = (if i…` accepted · committed state unchanged
_committing this would produce (remaining 2):_
```
Current goal (remaining: 2)
Type variables: <none>
&m: {}
i0: int
hi0: 0 <= i0 < N
------------------------------------------------------------------------
forall (z : int),
  phoare[ b <$ ${0,1}; ...; j <- j + 1; :
           ((0 <= j <= N /\
             i = i0 /\
             big predT<:int> a PIR.s +^ big predT<:int> a PIR.s' =
             if i0 < j then a i0 else zerow) /\
            j < N) /\
           N - j = z ==>
           (0 <= j <= N /\
            i = i0 /\
            big predT<:int> a PIR.s +^ big predT<:int> a PIR.s' =
            if i0 < j then a i0 else zerow) /\
           N - j < z] = 1%r
[23|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

