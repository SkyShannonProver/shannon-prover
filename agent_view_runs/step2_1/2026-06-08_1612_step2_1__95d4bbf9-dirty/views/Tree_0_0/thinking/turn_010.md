# Tree-0.0 · turn 10 · commit_tactic

<!-- session 97e6a0e6-3ebd-4e69-827b-9ef0ceb80f2b · 2026-06-08T23:19:52.787Z -->

**Intent:** `commit_tactic`  
**Payload:** `conseq (: _ ==> (glob A){1} = (glob A){2} /\ StLSke.gs{1} = OCC.gs{2} /\ Mem.k{1} = Mem.k{2}).`

---

`sim` can't bridge the differing global names (`StLSke.gs` vs `OCC.gs`). Let me first simplify the postcondition to just the invariant via `conseq`.
