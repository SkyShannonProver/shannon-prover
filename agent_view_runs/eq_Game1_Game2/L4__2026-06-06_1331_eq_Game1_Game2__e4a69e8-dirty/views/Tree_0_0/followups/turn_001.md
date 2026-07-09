## 🔍 Probe preview — `proc.` accepted · committed state unchanged
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
h <$ dptxt                      (6)  h <$ dptxt
c <-                            (7)  c <- (f pk Game2.r, h)
  (f pk Game1.r,                ( )
   h +^ if b then m0 else m1)   ( )
b' <@ A(Log(LRO)).a2(c)         (8)  b' <@ A(Log(LRO)).a2(c)
post =
  (Log.qs{1} = Log.qs{2} /\ (b'{1} = b{1}) = (b'{2} = b{2})) /\
  Game1.r{1} = Game2.r{2}
[75|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

