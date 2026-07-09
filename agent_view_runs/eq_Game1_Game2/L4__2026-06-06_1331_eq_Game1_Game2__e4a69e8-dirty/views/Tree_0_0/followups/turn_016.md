## 🔍 Probe preview — `conseq (_ : _ ==> ={glob A, Log.qs, LRO.m, pk, b} /\ Game1.r{1} = Game2.r{2}).` accepted · committed state unchanged
_committing this would produce (remaining 2):_
```
Current goal (remaining: 2)
Type variables: <none>
------------------------------------------------------------------------
forall &1 &2,
  (glob A){1} = (glob A){2} =>
  forall (A_L : (glob A)) (r_L : rand) (qs_L : rand list) (m_L : (rand,
    ptxt) fmap) (b_L : bool) (m0_L m1_L : ptxt) (pk_L : pkey)
    (A_R : (glob A)) (r_R : rand) (qs_R : rand list) (m_R : (rand,
    ptxt) fmap) (b_R : bool) (pk_R : pkey),
    (A_L = A_R /\ qs_L = qs_R /\ m_L = m_R /\ pk_L = pk_R /\ b_L = b_R) /\
    r_L = r_R =>
    (forall (hR : ptxt),
       hR \in dptxt =>
       hR = (hR +^ if b_L then m0_L else m1_L) +^ if b_L then m0_L else m1_L) &&
    (forall (hR : ptxt),
       hR \in dptxt =>
       mu1 dptxt hR = mu1 dptxt (hR +^ if b_L then m0_L else m1_L)) &&
    forall (hL : ptxt),
      hL \in dptxt =>
      ((hL +^ if b_L then m0_L else m1_L) \in dptxt) &&
      (hL = (hL +^ if b_L then m0_L else m1_L) +^ if b_L then m0_L else m1_L) &&
      ((f pk_L r_L, hL +^ if b_L then m0_L else m1_L) =
       (f pk_R r_R, hL +^ if b_L then m0_L else m1_L) /\
       A_L = A_R /\ qs_L = qs_R /\ m_L = m_R) &&
      forall (result_L result_R : bool) (A_L0 : (glob A)) (qs_L0 : rand list)
        (m_L0 : (rand, ptxt) fmap) (A_R0 : (glob A)) (qs_R0 : rand list)
        (m_R0 : (rand, ptxt) fmap),
        result_L = result_R /\ A_L0 = A_R0 /\ qs_L0 = qs_R0 /\ m_L0 = m_R0 =>
        (qs_L0 = qs_R0 /\ (result_L = b_L) = (result_R = b_R)) /\ r_L = r_R
[80|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

