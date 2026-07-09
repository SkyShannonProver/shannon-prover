# Tree-0.0 · turn 12 · commit_tactic

<!-- session 5a34e25e-6cb0-4b52-a73e-3dd4b84fb232 · 2026-06-06T12:53:28.438Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd (fun (z:exp) => z - e1{2}*w{2}) (fun (r:exp) => r + e1{2}*w{2}).`

---

I need to get the `rnd` bijection direction right. Let me check examples in the EasyCrypt theories.

`rnd f finv` couples `right = f(left)`. I want real `r = z1 - e·w`, inverse `z1 = r + e·w`.
