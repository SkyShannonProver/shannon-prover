# Tree-0.0 · turn 6 · commit_tactic

<!-- session 5a34e25e-6cb0-4b52-a73e-3dd4b84fb232 · 2026-06-06T12:48:28.849Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> w00 _; split=> _ r1 _ e6 _ z10 _; rewrite log_bij !(loggK, logDr, logrzM); ring.`

---

The goal is the group fact `g^z·X^(-e)·X^e = g^z`. Let me check the available group lemma names.

Group fact. I'll mirror the file's `log_bij` + ring idiom, applied to both branches.
