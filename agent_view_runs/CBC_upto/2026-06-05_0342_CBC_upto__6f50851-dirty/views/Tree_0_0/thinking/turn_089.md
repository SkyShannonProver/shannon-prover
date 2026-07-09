# Tree-0.0 · turn 89 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:47:33.310Z -->

**Intent:** `probe_tactic`  
**Payload:** `conseq (_: _ ==> true: =1%r) (_: _ ==> 0 <= i + 1 <= size p /\ size p - (i + 1) < z).`

---

`auto` wp'd the tail but left the body (ifs + conditional sample). The post depends only on `i,p` (frozen in the body), so I'll split into islossless + a hoare for the int post via conseq. Probing.
