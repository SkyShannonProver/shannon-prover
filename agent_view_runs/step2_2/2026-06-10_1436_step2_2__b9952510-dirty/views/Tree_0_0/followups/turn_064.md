## 🔍 Probe preview — `move: Hdec Hc Hn0; rewrite /dec /genpoly1305 /get /=; case: c => cn ca cc ct /=…` accepted · committed state unchanged
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
post =
  (0 <= i{2} <= size ns{2} /\
   Mem.lc{1} = Mem.lc{2} /\
   StLSke.gs{1} = RO.m{2} /\
   ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}) /\
   forall (c : ciphertext),
     c \in Mem.lc{2} =>
     dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes> =>
     c.`1 \in take i{2} ns{2} => forged{2}) /\
  forall (forged_R : bool) (i_R : int),
    ((0 <= i_R <= size ns{2} /\
      Mem.lc{1} = Mem.lc{2} /\
      StLSke.gs{1} = RO.m{2} /\
      ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}) /\
      forall (c : ciphertext),
        c \in Mem.lc{2} =>
        dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes> =>
        c.`1 \in take i_R ns{2} => forged_R) =>
     size ns{2} - i_R <= 0 => ! i_R < size ns{2}) /\
    (! i_R < size ns{2} =>
     (0 <= i_R <= size ns{2} /\
      Mem.lc{1} = Mem.lc{2} /\
      StLSke.gs{1} = RO.m{2} /\
      ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}) /\
      forall (c : ciphertext),
        c \in Mem.lc{2} =>
        dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes> =>
        c.`1 \in take i_R ns{2} => forged_R) =>
     (exists (c : ciphertext),
        (c \in Mem.lc{1}) /\
        dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes>) =>
     forged_R)
[323|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

