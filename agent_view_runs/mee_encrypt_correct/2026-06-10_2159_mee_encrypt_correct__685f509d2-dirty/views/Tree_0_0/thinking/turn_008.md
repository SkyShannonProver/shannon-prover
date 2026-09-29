# Tree-0.0 · turn 8 · commit_tactic

<!-- session f6525898-083c-4c36-8d4f-388aae59ebc6 · 2026-06-11T05:07:23.571Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp; rnd (fun v => v :: cbc_enc AES _ek v p' = _c); wp; skip => />.`

---

`skip` hit the remaining assignments 1–5 — need another `wp` after `rnd`.
