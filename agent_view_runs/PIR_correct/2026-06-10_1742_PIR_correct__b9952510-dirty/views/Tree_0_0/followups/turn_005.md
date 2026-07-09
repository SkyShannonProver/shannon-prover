## 🔍 Probe preview — `proc; inline *; wp; sp.` accepted · committed state unchanged
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
(1------)  while (j < N) {
(1.1----)    b <$ {0,1}
(1.2----)    if (j = i) {
(1.2.1--)      if (b) {
(1.2.1.1)        PIR.s <- j :: PIR.s
(1.2.1--)      } else {
(1.2.1?1)        PIR.s' <- j :: PIR.s'
(1.2.1--)      }
(1.2----)    } else {
(1.2?1--)      if (b) {
(1.2?1.1)        PIR.s <- j :: PIR.s
(1.2?1.2)        PIR.s' <- j :: PIR.s'
(1.2?1--)      }
(1.2----)    }
(1.3----)    j <- j + 1
(1------)  }
post = big predT<:int> a PIR.s +^ big predT<:int> a PIR.s' = a i0
[22|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

