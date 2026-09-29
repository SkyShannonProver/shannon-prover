# Tree-0.0 · turn 46 · lookup_symbol

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:04:09.472Z -->

**Intent:** `lookup_symbol`  
**Payload:** `test_poly`

---

The `forall` obligation is isolated. The key step: `take (i+1) ns = rcons (take i ns) n0`, so membership splits into the IH case (`c.\`1 \in take i ns`) and the new case (`c.\`1 = n0`). Let me look up `test_poly` to understand the new case's content.
