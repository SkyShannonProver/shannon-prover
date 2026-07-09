# Tree-0.0 · turn 8 · probe_tactic

<!-- session e60e6dbc-412b-42a6-ac10-5ce092bc8486 · 2026-06-09T18:52:42.553Z -->

**Intent:** `probe_tactic`  
**Payload:** `rcondf{1} 28.`

---

I have the complete inlined picture. My plan:
- **Left (ideal)** samples: w0, r(dead), e, z1; transcript m0=g^z1·x^(−e), z=z1
- **Right (real)** samples: w0, r, e1; transcript m0=g^r, z=r+e·w0
- Coupling: z1 ↔ r via z1 = r + e·w0; left's r is dead; the while loop never runs (verify always true).

Let me first kill the left while loop with `rcondf` (verify always succeeds, so `to <> None`).
