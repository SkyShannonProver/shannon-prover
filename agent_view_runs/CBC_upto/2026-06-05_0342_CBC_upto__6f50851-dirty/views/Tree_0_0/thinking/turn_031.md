# Tree-0.0 · turn 31 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:12:26.867Z -->

**Intent:** `probe_tactic`  
**Payload:** `if{1}; auto; smt(dBlock_uffu).`

---

Now a one-sided LHS residual: `if(x∈qs){bad<-true}; x0<-x; if(x0∉PRFi.m){r0<$dBlock;...}` with a losslessness/`bad{1}` post. `bad{1}` is true (from pre) and only ever set; `is_lossless dBlock` from `dBlock_uffu`. Let me probe handling the leading LHS `if` then auto+smt.
