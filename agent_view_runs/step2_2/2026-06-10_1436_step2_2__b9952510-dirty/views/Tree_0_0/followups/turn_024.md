## 🔍 Probe preview — `inline {2} 1.` accepted · committed state unchanged
_committing this would produce (remaining 3):_
```
Current goal (remaining: 3)
Type variables: <none>
&m: {}
------------------------------------------------------------------------
&1 (left ) : {r : bool}
&2 (right) : {r, forged : bool, i : int, n : nonce, ns : nonce list,
             r0 : poly_in, s : poly_out, bl : block}
pre = (glob A){1} = (glob A){2}
r <@ UFCMA(A, St).main()   (1--)  CPA_game(CCA_CPA_Adv(A),
                           (  -)    RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main()
                           (2--)  ns <-
                           (  -)    undup
                           (  -)      (map (fun (p : ciphertext) => p.`1)
                           (  -)         Mem.lc)
                           (3--)  forged <- false
                           (4--)  i <- 0
                           (5--)  while (i < size ns) {
                           (5.1)    n <- nth witness<:nonce> ns i
                           (5.2)    bl <@ FinRO.get(n, C.ofintd 0)
                           (5.3)    (r0, s) <- mk_rs bl
                           (5.4)    forged <-
                           (   )      forged || test_poly n Mem.lc r0 s
                           (5.5)    i <- i + 1
                           (5--)  }
                           (6--)  r <- forged
post =
  (exists (c : ciphertext),
     (c \in Mem.lc{1}) /\
     dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes>) =>
  r{2}
[310|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

