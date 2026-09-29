# Tree-0.1 · turn 1 · commit_tactic

<!-- session 859e1346-5a59-4c83-b788-4fa4b006529c · 2026-06-11T08:53:21.287Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc; inline *; wp; skip => />.`

---

I'll load the proof intent tool, then start on `poly_spec` — the body is deterministic (cc is a pure operator call), so this should reduce to `proc; inline; wp; skip` plus unfolding `genpoly1305`.
