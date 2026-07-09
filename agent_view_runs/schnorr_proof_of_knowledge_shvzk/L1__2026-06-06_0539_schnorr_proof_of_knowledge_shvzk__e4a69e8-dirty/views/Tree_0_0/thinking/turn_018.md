# Tree-0.0 · turn 18 · commit_tactic

<!-- session 5a34e25e-6cb0-4b52-a73e-3dd4b84fb232 · 2026-06-06T12:56:24.950Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> w0L _; split=> _ r1 _ eL _; (split; first by move=> rR _; ring); move=> _ z1L _; split; first by ring; move=> _; rewrite log_bij !(loggK, logDr, logrzM); ring.`

---

Pure algebra now: ring identities plus the group equation (same `log_bij` idiom). Both branches are isomorphic.
