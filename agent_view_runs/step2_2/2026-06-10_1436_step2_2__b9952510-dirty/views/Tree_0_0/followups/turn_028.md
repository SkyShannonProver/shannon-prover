## 🔍 Probe preview — `call UFCMA_genCC.` accepted · committed state unchanged
_committing this would produce (remaining 4):_
```
Current goal (remaining: 4)
Type variables: <none>
&m: {}
------------------------------------------------------------------------
&1 (left ) : {r : bool}
&2 (right) : {r, forged : bool, i : int, n : nonce, ns : nonce list,
             r0 : poly_in, s : poly_out, bl : block}
pre = (glob A){1} = (glob A){2}
post =
  (glob A){1} = (glob A){2} &&
  forall (result_L result_R : bool) (lc_L : ciphertext list) (gs_L : globS)
    (m_R : (nonce * C.counter, block) fmap) (lc_R : ciphertext list),
    (result_L = result_R /\ lc_L = lc_R) /\ gs_L = m_R =>
    lc_L = lc_R /\ gs_L = m_R
[312|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

