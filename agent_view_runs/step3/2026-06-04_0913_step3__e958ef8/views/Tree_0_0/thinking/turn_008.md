# Tree-0.0 · turn 8 · probe_tactic

<!-- session 85d57332-b3ec-4f7b-92f2-424aa26a1fe9 · 2026-06-04T16:17:31.298Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline*.`

---

Let me read the post-probe goal to see what the G8 inline produced.

Inline of G8 works. Rather than inline each wrapper individually, the abstract adversary `A` won't be inlined by `inline*` (its body is opaque), so `inline*` will stop at the `A(...).main` call on both sides — exposing the same abstract adversary with differing oracle modules. Let me probe `inline*` on both sides.
