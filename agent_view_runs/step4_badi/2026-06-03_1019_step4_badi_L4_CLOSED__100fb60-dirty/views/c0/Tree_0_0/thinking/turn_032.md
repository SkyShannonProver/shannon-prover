# Tree-0.0 · turn 32 · commit_tactic

<!-- session 7d6b85e1-efc5-4558-ab30-99a9e554877b · 2026-06-03T17:46:52.848Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline*.`

---

Let me read the full inlined expansion preview.

I now have the complete picture. Statements 1–11 (deterministic + while + `lt`) and 14–26 (RO/log/return) are identical; only statement 13 differs, and the sample `t0` (12) must be coupled carefully (in-range, `{2}` resamples `t1` and discards the outer `t0`). Let me commit `inline*` and then test how much `sim` can absorb.
