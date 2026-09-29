## 🔍 Probe preview — `proc.` accepted · committed state unchanged
_committing this would produce (remaining 4):_
```
Current goal (remaining: 4)
Type variables: <none>
&m: {}
------------------------------------------------------------------------
&1 (left ) : {b : bool}
&2 (right) : {b : bool}
pre = (glob A){1} = (glob A){2}
RealOrcls(StLSke(St)).init()                    (1)  RealOrcls(GenChaChaPoly(CCRO(FinRO))).init()
b <@                                            (2)  b <@
  CCA_CPA_Adv(A, RealOrcls(StLSke(St))).main()  ( )    CCA_CPA_Adv(A,
                                                ( )      RealOrcls(
                                                ( )        GenChaChaPoly(CCRO(FinRO)))).main()
post = b{1} = b{2}
[304|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

