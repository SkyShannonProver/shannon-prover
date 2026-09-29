# Tree-0.0 · turn 35 · commit_tactic

<!-- session 04f2da79-838f-426c-bf2c-64746dff5b0e · 2026-06-10T21:57:32.860Z -->

**Intent:** `commit_tactic`  
**Payload:** `while{2} (0 <= i{2} <= size ns{2} /\ Mem.lc{1} = Mem.lc{2} /\ StLSke.gs{1} = RO.m{2} /\ ns{2} = undup (map (fun (p:ciphertext) => p.`1) Mem.lc{2}) /\ (forall (c:ciphertext), c \in Mem.lc{2} => dec StLSke.gs{1} Mem.k{1} c <> None => (c.`1 \in take i{2} ns{2}) => forged{2})) (size ns{2} - i{2}).`

---

The body subgoal confirms the structure but exposes the precise gap: for a forgery nonce `n`, proving `forged` becomes true needs `(n,0) ∈ dom StLSke.gs` (domain coverage), which isn't in scope. Let me check what `St` concretely is in this section — it may make coverage trivial.

St uses `FinRO` (FinEager RO). If `FinRO` initializes a **total** map eagerly, domain coverage is trivial and `RO.m` never changes during the loop. Let me verify the `FinRO`/`FinEager` semantics.

Let me confirm `FinRO.get` semantics from the PROM/FinEager library.

Confirmed: `FinRO.get` is `return oget RO.m.[x]` — it does **not** modify `RO.m`, and `FinRO.init` eagerly fills the entire finite domain. So `RO.m` is total and constant through the loop: domain coverage is trivial and `StLSke.gs{1}=RO.m{2}` is preserved. This makes the loop body provable. Let me commit the clean invariant.
