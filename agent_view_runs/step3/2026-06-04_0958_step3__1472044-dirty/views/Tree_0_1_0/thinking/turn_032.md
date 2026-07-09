# Tree-0.1.0 · turn 32 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:42:01.272Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline *.`

---

Both sides: `p ← None; if check_cipher { p ← CPA_CCA_Orcls(_).dec(c); ndec++ }`. The reduction's dec just logs the ciphertext and returns None (doesn't touch RO maps), so the bodies match. Inline both dec wrappers to confirm.
