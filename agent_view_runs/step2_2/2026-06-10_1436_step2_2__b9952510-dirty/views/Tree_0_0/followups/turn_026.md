## 🔍 Probe preview — `seq 1 1 : (={Mem.lc} /\ StLSke.gs{1} = RO.m{2}).` accepted · committed state unchanged
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
r <@ UFCMA(A, St).main()   (1)  CPA_game(CCA_CPA_Adv(A),
                           ( )    RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main()
post = Mem.lc{1} = Mem.lc{2} /\ StLSke.gs{1} = RO.m{2}
[311|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

