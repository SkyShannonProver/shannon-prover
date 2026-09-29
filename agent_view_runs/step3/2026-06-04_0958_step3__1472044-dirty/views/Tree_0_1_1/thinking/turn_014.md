# Tree-0.1.1 · turn 14 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:39:42.758Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

I had the direction wrong — EC reasons backward from the *last* statement, which is the deterministic `t <- poly1305 ...`, not the leading `r5` sample. Let me consume the trailing deterministic assignments with `wp` and see where it stops.
