# Tree-0.1.0 · turn 6 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:24:16.580Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

Closed the cc side-condition (5→4 remaining). Now at the Poly-mac vs random-tag coupling: left computes `t` via `Poly.mac` (which samples the RO block at counter 0, extracts `(r,s)`, returns `s + poly1305_eval r p`), right samples `t <$ dpoly_out`. I need to couple these. First absorb the trailing assignments with `wp`.
