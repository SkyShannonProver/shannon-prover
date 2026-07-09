# Tree-0.0 · turn 32 · commit_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:45:31.096Z -->

**Intent:** `commit_tactic`  
**Payload:** `split; first by smt(). rewrite -Heq (gen_CTR_encrypt_bytes_cons take_xor (cc gs0) k0 n0 i{hr} p{hr} Hnil) /take_xor catA //.`

---

The loop **body obligation is fully discharged**. Remaining goal 1 is the prefix (`c<-[]; i<-1`) + entry/exit conditions from the `while`. Let me commit this.
