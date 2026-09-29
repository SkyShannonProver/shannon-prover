# Tree-0.0 · turn 34 · probe_tactic

<!-- session 04f2da79-838f-426c-bf2c-64746dff5b0e · 2026-06-10T21:55:44.596Z -->

**Intent:** `probe_tactic`  
**Payload:** `while{2} (0 <= i{2} <= size ns{2} /\ Mem.lc{1} = Mem.lc{2} /\ ns{2} = undup (map (fun (p:ciphertext) => p.`1) Mem.lc{2}) /\ (forall x, x \in StLSke.gs{1} => RO.m{2}.[x] = StLSke.gs{1}.[x]) /\ (forall (c:ciphertext), c \in Mem.lc{2} => dec StLSke.gs{1} Mem.k{1} c <> None => (c.`1 \in take i{2} ns{2}) => forged{2})) (size ns{2} - i{2}).`

---

The one-sided `while` form works. Now let me probe the real invariant: tracking RO-monotonicity plus "forged covers all forgeries whose nonce is already processed."
