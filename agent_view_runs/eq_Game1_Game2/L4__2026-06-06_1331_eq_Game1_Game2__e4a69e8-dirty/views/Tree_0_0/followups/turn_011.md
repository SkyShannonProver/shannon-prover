## 🔍 Probe preview — `rnd (fun (x : ptxt) => x +^ (if b{1} then m0{1} else m1{1})).` accepted · committed state unchanged
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
  (forall (hR : ptxt),
     hR \in dptxt =>
     hR =
     (hR +^ if b{1} then m0{1} else m1{1}) +^ if b{1} then m0{1} else m1{1}) &&
  (forall (hR : ptxt),
     hR \in dptxt =>
     mu1 dptxt hR = mu1 dptxt (hR +^ if b{1} then m0{1} else m1{1})) &&
  forall (hL : ptxt),
    hL \in dptxt =>
    ((hL +^ if b{1} then m0{1} else m1{1}) \in dptxt) &&
    (hL =
     (hL +^ if b{1} then m0{1} else m1{1}) +^ if b{1} then m0{1} else m1{1}) &&
    ((f pk{1} Game1.r{1}, hL +^ if b{1} then m0{1} else m1{1}) =
     (f pk{2} Game2.r{2}, hL +^ if b{1} then m0{1} else m1{1}) /\
     (glob A){1} = (glob A){2} /\
     Log.qs{1} = Log.qs{2} /\ LRO.m{1} = LRO.m{2}) &&
    forall (result_L result_R : bool) (A_L : (glob A)) (qs_L : rand list)
      (m_L : (rand, ptxt) fmap) (A_R : (glob A)) (qs_R : rand list)
      (m_R : (rand, ptxt) fmap),
      result_L = result_R /\ A_L = A_R /\ qs_L = qs_R /\ m_L = m_R =>
      (qs_L = qs_R /\ (result_L = b{1}) = (result_R = b{2})) /\
      Game1.r{1} = Game2.r{2}
[79|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

