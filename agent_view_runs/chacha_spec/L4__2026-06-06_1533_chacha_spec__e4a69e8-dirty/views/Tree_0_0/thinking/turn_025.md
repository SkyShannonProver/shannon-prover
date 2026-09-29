# Tree-0.0 · turn 25 · commit_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:44:22.486Z -->

**Intent:** `commit_tactic`  
**Payload:** `have Hnil: forall s, take_xor [] s = [].`

---

No EC error recorded — the probe dry-run mechanism is choking on this `have ... by ...` form. Let me commit the `have` without the inline `by`, producing the helper as a separate subgoal I prove next.
