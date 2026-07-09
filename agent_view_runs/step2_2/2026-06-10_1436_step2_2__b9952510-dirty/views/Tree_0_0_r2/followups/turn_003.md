## 🔍 Probe preview — `move=> Hexit [i_rng [Hlc' [Hgs' [Hns' IH]]]] [c [Hc Hdec]].` accepted · committed state unchanged
_committing this would produce (remaining 3):_
```
Current goal (remaining: 3)
Type variables: <none>
&m: {}
&1: {r : bool}
&2: {r, forged : bool, i : int, n : nonce, ns : nonce list, r0 : poly_in,
    s : poly_out, bl : block}
Hns: ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2})
Hf: forged{2} = false
Hi: i{2} = 0
Hlc: Mem.lc{1} = Mem.lc{2}
Hgs: StLSke.gs{1} = RO.m{2}
forged_R: bool
i_R: int
Hexit: ! i_R < size ns{2}
i_rng: 0 <= i_R <= size ns{2}
Hlc': Mem.lc{1} = Mem.lc{2}
Hgs': StLSke.gs{1} = RO.m{2}
Hns': ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2})
IH: forall (c : ciphertext),
      c \in Mem.lc{2} =>
      dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes> =>
      c.`1 \in take i_R ns{2} => forged_R
c: ciphertext
Hc: c \in Mem.lc{1}
Hdec: dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes>
------------------------------------------------------------------------
forged_R
[327|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

