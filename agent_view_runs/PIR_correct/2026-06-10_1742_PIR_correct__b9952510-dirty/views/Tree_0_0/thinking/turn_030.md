# Tree-0.0 · turn 30 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:54:45.707Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite BBS.big_cons /=.`

---

Genuine no-op — `rewrite big_cons` isn't matching, likely the ambiguous clone instance. Let me probe the qualified `BBS.big_cons` alone to confirm it rewrites.
