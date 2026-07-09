# Tree-0.0 · turn 31 · probe_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:45:15.978Z -->

**Intent:** `probe_tactic`  
**Payload:** `split; first by smt(). rewrite -Heq (gen_CTR_encrypt_bytes_cons take_xor (cc gs0) k0 n0 i{hr} p{hr} Hnil) /take_xor catA //.`

---

Now `1 <= i+1 /\ MAINEQ`. Let me probe the complete remaining close in one shot: split off the easy conjunct, then the rewrite chain for the main equality.
