# Tree-0.0 · turn 39 · probe_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:47:48.093Z -->

**Intent:** `probe_tactic`  
**Payload:** `split; first by rewrite eqk eqn eqgs eqp /=. move=> c0 i0 p1; split; first by smt(size_ge0 size_eq0). by move=> ->; rewrite (gen_CTR_encrypt_bytes0 take_xor (cc gs0) k0 n0 i0 Hnil) cats0; smt().`

---

Now let me probe the full closing of all three parts.
