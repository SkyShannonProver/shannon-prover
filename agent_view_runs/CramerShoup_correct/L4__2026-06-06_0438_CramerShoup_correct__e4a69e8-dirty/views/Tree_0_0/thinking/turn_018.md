# Tree-0.0 · turn 18 · lookup_symbol

<!-- session 5234f886-6033-4a40-9812-c27131140e4b · 2026-06-06T11:46:42.322Z -->

**Intent:** `lookup_symbol`  
**Payload:** `expN`

---

`smt(@DH.G)` can't do it. The robust fix: convert `inv` into a `g^(...)` form so no `inv` atom survives, then `log_bij; ring` closes. The hint named `expN` for group inverses. Let me look it up.
