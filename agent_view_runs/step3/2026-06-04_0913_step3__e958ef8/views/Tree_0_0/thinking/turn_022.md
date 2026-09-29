# Tree-0.0 · turn 22 · probe_tactic

<!-- session 85d57332-b3ec-4f7b-92f2-424aa26a1fe9 · 2026-06-04T16:25:33.948Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline{2} CPA_CCA_Orcls(EncRnd).enc EncRnd.enc.`

---

`CPA_CCA_Orcls(S).enc` = `p0<-p; c0<@S.enc(p0); Mem.log.[c0<-p0]; c<-c0`. On the right I also need `EncRnd.enc` inlined to expose its `cc` call. Let me probe inlining both right-side wrappers.
