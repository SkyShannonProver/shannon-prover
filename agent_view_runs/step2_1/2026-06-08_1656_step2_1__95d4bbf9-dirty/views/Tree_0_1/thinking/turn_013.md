# Tree-0.1 · turn 13 · commit_tactic

<!-- session a7472aaf-be97-4058-b42c-c8c823c1a2a1 · 2026-06-09T00:02:59.299Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &2.`

---

The unfold didn't fire — likely `enc` is ambiguous (several `enc` ops in scope). Let me intro `&2` first and inspect the goal head, then unfold precisely.
