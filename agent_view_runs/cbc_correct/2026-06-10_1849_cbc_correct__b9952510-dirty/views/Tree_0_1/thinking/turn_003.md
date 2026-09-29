# Tree-0.1 · turn 3 · probe_tactic

<!-- session bf074102-6b84-43e0-81d9-f333aa8f901f · 2026-06-11T01:50:46.265Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite kK ih; split=> //; rewrite xorbC xorbA xorbK xorbC xorb0.`

---

Now `rewrite kK ih` should collapse the second conjunct and reduce the first to an xor identity. Let me probe the full close.
