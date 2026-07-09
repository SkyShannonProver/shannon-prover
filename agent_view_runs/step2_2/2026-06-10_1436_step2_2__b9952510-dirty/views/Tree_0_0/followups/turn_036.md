## 🔍 Probe preview — `move=> &m0 z; inline FinRO.get; wp; skip.` accepted · committed state unchanged
_committing this would produce (remaining 4):_
```
Current goal (remaining: 4)
Type variables: <none>
&m: {}
&m0: {r : bool}
z: int
------------------------------------------------------------------------
forall &hr,
  ((0 <= i{hr} <= size ns{hr} /\
    Mem.lc{m0} = Mem.lc{hr} /\
    StLSke.gs{m0} = RO.m{hr} /\
    ns{hr} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr}) /\
    forall (c : ciphertext),
      c \in Mem.lc{hr} =>
      dec StLSke.gs{m0} Mem.k{m0} c <> None<:nonce * associated_data * bytes> =>
      c.`1 \in take i{hr} ns{hr} => forged{hr}) /\
   i{hr} < size ns{hr}) /\
  size ns{hr} - i{hr} = z =>
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
[316|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

