## 🔍 Probe preview — `while{2} (0 <= i{2} <= size ns{2} /\ Mem.lc{1} = Mem.lc{2} /\ ns{2} = undup (ma…` accepted · committed state unchanged
_committing this would produce (remaining 4):_
```
Current goal (remaining: 4)
Type variables: <none>
&m: {}
------------------------------------------------------------------------
forall &m0 (z : int),
  phoare[ n <- nth witness<:nonce> ns i; ...; i <- i + 1; :
           ((0 <= i <= size ns /\
             Mem.lc{m0} = Mem.lc /\
             ns = undup (map (fun (p : ciphertext) => p.`1) Mem.lc) /\
             (forall (x : nonce * C.counter),
                x \in StLSke.gs{m0} => RO.m.[x] = StLSke.gs{m0}.[x]) /\
             forall (c : ciphertext),
               c \in Mem.lc =>
               dec StLSke.gs{m0} Mem.k{m0} c <> None<:nonce *
               associated_data * bytes> => c.`1 \in take i ns => forged) /\
            i < size ns) /\
           size ns - i = z ==>
           (0 <= i <= size ns /\
            Mem.lc{m0} = Mem.lc /\
            ns = undup (map (fun (p : ciphertext) => p.`1) Mem.lc) /\
            (forall (x : nonce * C.counter),
               x \in StLSke.gs{m0} => RO.m.[x] = StLSke.gs{m0}.[x]) /\
            forall (c : ciphertext),
              c \in Mem.lc =>
              dec StLSke.gs{m0} Mem.k{m0} c <> None<:nonce *
              associated_data * bytes> => c.`1 \in take i ns => forged) /\
           size ns - i < z] = 1%r
[315|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

