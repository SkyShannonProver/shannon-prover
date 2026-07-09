## 🔍 Probe preview — `move=> &hr [[H Hlt] Hz]; case: H => i_rng [Hlc [Hgs [Hns IH]]].` accepted · committed state unchanged
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
------------------------------------------------------------------------
let n0 = nth witness<:nonce> ns{hr} i{hr} in
let tpl = mk_rs (oget RO.m{hr}.[n0, C.ofintd 0]) in
let i0 = i{hr} + 1 in
(0 <= i0 <= size ns{hr} /\
 Mem.lc{m0} = Mem.lc{hr} /\
 StLSke.gs{m0} = RO.m{hr} /\
 ns{hr} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr}) /\
 forall (c : ciphertext),
   c \in Mem.lc{hr} =>
   dec StLSke.gs{m0} Mem.k{m0} c <> None<:nonce * associated_data * bytes> =>
   c.`1 \in take i0 ns{hr} =>
   forged{hr} || test_poly n0 Mem.lc{hr} tpl.`1 tpl.`2) /\
size ns{hr} - i0 < z
[317|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

