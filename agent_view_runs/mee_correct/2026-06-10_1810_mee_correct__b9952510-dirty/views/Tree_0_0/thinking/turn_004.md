# Tree-0.0 · turn 4 · probe_tactic

<!-- session cdc7c7dc-126c-4234-badf-079855e9c803 · 2026-06-11T01:11:33.043Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite (cbc_correct P Pi ek iv (pad m (M mk m)) hPi) padK /=.`

---

`cbc_correct` recovers `pad m (M mk m)`. Now `padK` resolves the unpad and the MAC check is reflexive. Let me probe the closing.
