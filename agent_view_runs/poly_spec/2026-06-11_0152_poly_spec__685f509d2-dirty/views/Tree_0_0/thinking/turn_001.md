# Tree-0.0 · turn 1 · commit_tactic

<!-- session ec3b004d-4cff-4a81-8e3d-d5bdc8fc9a30 · 2026-06-11T08:53:01.913Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

The goal is a phoare spec for `Poly(OCC(I)).mac`, whose body is a deterministic call to `OCC(I).cc` (which just returns `cc OCC.gs k n c`) followed by assignments. Plan: `proc`, inline the cc call, `wp`/`skip`, then unfold `genpoly1305`.
