## 🔍 Probe preview — `smt(addpK dptxt_funi dptxt_fu).` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
------------------------------------------------------------------------
&1 (left ) : {b, b' : bool, m0, m1, h : ptxt, c : rand * ptxt, pk : pkey,
             sk : skey}
&2 (right) : {b, b' : bool, m0, m1, h : ptxt, c : rand * ptxt, pk : pkey,
             sk : skey}
pre = (glob A){1} = (glob A){2}
Log(LRO).init()                 (1)  Log(LRO).init()
(pk, sk) <$ dkeys               (2)  (pk, sk) <$ dkeys
(m0, m1) <@ A(Log(LRO)).a1(pk)  (3)  (m0, m1) <@ A(Log(LRO)).a1(pk)
b <$ {0,1}                      (4)  b <$ {0,1}
Game1.r <$ drand                (5)  Game2.r <$ drand
post =
  ((glob A){1} = (glob A){2} /\
   Log.qs{1} = Log.qs{2} /\
   LRO.m{1} = LRO.m{2} /\ pk{1} = pk{2} /\ b{1} = b{2}) /\
  Game1.r{1} = Game2.r{2}
[81|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

