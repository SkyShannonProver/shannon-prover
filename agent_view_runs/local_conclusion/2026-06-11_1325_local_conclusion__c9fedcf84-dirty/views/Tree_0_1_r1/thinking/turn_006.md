# Tree-0.1.r1 · turn 6 · commit_tactic

<!-- session ee589c25-2d68-4d07-a5d2-61c45dae1522 · 2026-06-11T20:50:41.882Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> O O_enc_ll; proc.`

---

There's a `section Losslessness` in RCPA_CMA.ec — let me check for ready-made lemmas, plus the MAC module body.

The structure is clear. `MAC.keygen` samples `d_mK`; let me check the lossless axiom name for `d_mK`.

`d_mK_uffu` gives losslessness. Now the losslessness proof, step by step: intro and `proc` first.
