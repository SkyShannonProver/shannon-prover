# Tree-0.0 · turn 13 · unknown

<!-- session 3ad27182-af4d-4241-bfd6-16292deaeaf6 · 2026-06-04T16:31:51.186Z -->

**Intent:** ``  
**Payload:** `(none)`

---

Core goal: `mu D (fun r=>finv r=a)` vs `if 1<=a<=4 then 1/4 else 0`. On D's support `{1,2,3,4}`, `finv r = a ⟺ r = f a` (for all `a`). So I can rewrite the predicate to `pred1 (f a)` with no case split. Let me check `mu_eq_support`'s exact form.

`mu_eq_support` needs pointwise equality on the support. Let me rewrite the predicate to `pred1 (f a)`.
