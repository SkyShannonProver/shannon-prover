# Tree-0.0 · turn 26 · probe_tactic

<!-- session 04f2da79-838f-426c-bf2c-64746dff5b0e · 2026-06-10T21:50:47.521Z -->

**Intent:** `probe_tactic`  
**Payload:** `seq 1 1 : (={Mem.lc} /\ StLSke.gs{1} = RO.m{2}).`

---

Now I need to understand `dec`, `genpoly1305`, `mk_rs`, and `test_poly` to build the loop invariant. Let me read those definitions.

The math checks out: `get` ignores the key, and `genpoly1305`/`mk_rs` on the LHS matches `test_poly` with `bl=RO.get(n,0)` on the RHS when `StLSke.gs{1}=RO.m{2}`. Let me set up the seq split at the call boundary using the `UFCMA_genCC` coupling.
