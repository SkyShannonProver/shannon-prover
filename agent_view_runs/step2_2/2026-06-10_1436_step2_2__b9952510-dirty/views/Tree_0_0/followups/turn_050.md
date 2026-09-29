## 🔍 Probe preview — `move=> [Hn0 | Hold]; last by have := IH c Hc Hdec Hold; smt().` accepted · committed state unchanged
_committing this would produce (remaining 4):_
```
Current goal (remaining: 4)
Type variables: <none>
&m: {}
&m0: {r : bool}
z: int
&hr: {r, forged : bool, i : int, n : nonce, ns : nonce list,
     x : nonce * C.counter, r0 : poly_in, s : poly_out, bl : block}
Hlt: i{hr} < size ns{hr}
Hz: size ns{hr} - i{hr} = z
i_rng: 0 <= i{hr} <= size ns{hr}
Hlc: Mem.lc{m0} = Mem.lc{hr}
Hgs: StLSke.gs{m0} = RO.m{hr}
Hns: ns{hr} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr})
IH: forall (c : ciphertext),
      c \in Mem.lc{hr} =>
      dec StLSke.gs{m0} Mem.k{m0} c <> None<:nonce * associated_data * bytes> =>
      c.`1 \in take i{hr} ns{hr} => forged{hr}
c: ciphertext
Hc: c \in Mem.lc{hr}
Hdec: dec StLSke.gs{m0} Mem.k{m0} c <> None<:nonce * associated_data * bytes>
Hn0: c.`1 = nth witness<:nonce> ns{hr} i{hr}
------------------------------------------------------------------------
forged{hr} ||
test_poly (nth witness<:nonce> ns{hr} i{hr}) Mem.lc{hr}
  (mk_rs (oget RO.m{hr}.[nth witness<:nonce> ns{hr} i{hr}, C.ofintd 0])).`1
  (mk_rs (oget RO.m{hr}.[nth witness<:nonce> ns{hr} i{hr}, C.ofintd 0])).`2
[321|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

