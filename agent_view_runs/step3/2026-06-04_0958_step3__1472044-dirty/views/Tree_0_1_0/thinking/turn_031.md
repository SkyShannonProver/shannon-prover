# Tree-0.1.0 · turn 31 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:41:27.378Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

The big enc obligation is fully done. Remaining 2: this is the `dec` oracle obligation from the adversary `call` invariant. In the CPA→CCA reduction the dec oracle just records the ciphertext and returns `None` (it doesn't touch the RO maps), so both sides should run identical code preserving `inv_cpa`. Let me open the procedure to confirm the body.
