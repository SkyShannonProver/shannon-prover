## 🔍 Probe preview — `sp; wp.` accepted · committed state unchanged
_committing this would produce (remaining 3):_
```
Current goal (remaining: 3)
Type variables: <none>
&m: {}
------------------------------------------------------------------------
&1 (left ) : {r : bool}
&2 (right) : {r, forged : bool, i : int, n : nonce, ns : nonce list,
             r0 : poly_in, s : poly_out, bl : block}
pre =
  ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}) /\
  forged{2} = false /\
  i{2} = 0 /\ Mem.lc{1} = Mem.lc{2} /\ StLSke.gs{1} = RO.m{2}
                           (1--)  while (i < size ns) {
                           (1.1)    n <- nth witness<:nonce> ns i
                           (1.2)    bl <@ FinRO.get(n, C.ofintd 0)
                           (1.3)    (r0, s) <- mk_rs bl
                           (1.4)    forged <-
                           (   )      forged || test_poly n Mem.lc r0 s
                           (1.5)    i <- i + 1
                           (1--)  }
post =
  (exists (c : ciphertext),
     (c \in Mem.lc{1}) /\
     dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes>) =>
  forged{2}
[314|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

