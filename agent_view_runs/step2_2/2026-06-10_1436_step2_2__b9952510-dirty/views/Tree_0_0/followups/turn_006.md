## 🔍 Probe preview — `byequiv (_: ={glob A} ==> ={res}).` accepted · committed state unchanged
_committing this would produce (remaining 4):_
```
Current goal (remaining: 4)
Type variables: <none>
&m: {}
------------------------------------------------------------------------
pre = (glob A){1} = (glob A){2}
    CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main ~ CPA_game(
                                                             CCA_CPA_Adv(A),
                                                             RealOrcls(
                                                               GenChaChaPoly(
                                                                 CCRO(FinRO)))).main
post = res{1} = res{2}
[303|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

