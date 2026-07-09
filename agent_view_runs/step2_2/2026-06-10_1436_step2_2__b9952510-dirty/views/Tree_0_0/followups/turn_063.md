## 🔍 Probe preview — `move: Hdec; rewrite /dec /genpoly1305 /get /=.` accepted · committed state unchanged
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
Hn0: c.`1 = nth witness<:nonce> ns{hr} i{hr}
------------------------------------------------------------------------
(let (n0, a, c0, t) = c in
 if t =
    let (r1, s0) = mk_rs (oget StLSke.gs{m0}.[n0, C.ofintd 0]) in
    poly1305 r1 s0 (topol a c0) then
   Some
     (n0, a,
      gen_CTR_encrypt_bytes take_xor
        (fun (_ : key) (n1 : nonce) (c1 : C.counter) =>
           oget StLSke.gs{m0}.[n1, c1]) Mem.k{m0} n0 1 c0)
 else None<:nonce * associated_data * bytes>) <>
None<:nonce * associated_data * bytes> =>
c.`4 =
poly1305
  (mk_rs (oget RO.m{hr}.[nth witness<:nonce> ns{hr} i{hr}, C.ofintd 0])).`1
  (mk_rs (oget RO.m{hr}.[nth witness<:nonce> ns{hr} i{hr}, C.ofintd 0])).`2
  (topol c.`2 c.`3)
[323|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

