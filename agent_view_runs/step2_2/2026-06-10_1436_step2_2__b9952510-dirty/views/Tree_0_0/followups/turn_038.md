## 🔍 Probe preview — `move=> &hr [[H Hlt] Hz]; case: H => i_rng eqlc eqgs eqns Hold.` accepted · committed state unchanged
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
eqlc: Mem.lc{m0} = Mem.lc{hr} /\
      StLSke.gs{m0} = RO.m{hr} /\
      ns{hr} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr}) /\
      forall (c : ciphertext),
        c \in Mem.lc{hr} =>
        dec StLSke.gs{m0} Mem.k{m0} c <> None<:nonce * associated_data *
        bytes> => c.`1 \in take i{hr} ns{hr} => forged{hr}
eqgs: nonce := nth witness<:nonce> ns{hr} i{hr}
eqns: poly_in * poly_out := mk_rs (oget RO.m{hr}.[eqgs, C.ofintd 0])
Hold: int := i{hr} + 1
------------------------------------------------------------------------
(0 <= Hold <= size ns{hr} /\
 Mem.lc{m0} = Mem.lc{hr} /\
 StLSke.gs{m0} = RO.m{hr} /\
 ns{hr} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr}) /\
 forall (c : ciphertext),
   c \in Mem.lc{hr} =>
   dec StLSke.gs{m0} Mem.k{m0} c <> None<:nonce * associated_data * bytes> =>
   c.`1 \in take Hold ns{hr} =>
   forged{hr} || test_poly eqgs Mem.lc{hr} eqns.`1 eqns.`2) /\
size ns{hr} - Hold < z
[317|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

