# Tree-0.1 · turn 4 · commit_tactic

<!-- session 71eefeb0-ba0c-4a92-8c5d-eb48f1c8df06 · 2026-06-09T04:00:03.340Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{2} 8.`

---

The right side now ends in a `FinRO.get` sample. I need to know whether `FinRO.get` is the eager (deterministic, full-map) variant or the lazy one. Let me check how `FinRO`/`FRO` are defined and used.

`FinRO` is the concrete RO passed into `CCRO`. Let me inline the `FinRO.get` call to see whether it samples (lazy) or just reads `m` (eager).
