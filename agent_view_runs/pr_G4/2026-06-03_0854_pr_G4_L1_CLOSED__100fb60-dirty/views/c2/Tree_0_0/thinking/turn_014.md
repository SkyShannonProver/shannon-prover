# Tree-0.0 · turn 14 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:03:13.087Z -->

**Intent:** `commit_tactic`  
**Payload:** `smt(size_ge0).`

---

The residual is pure arithmetic but needs `size (ci :: l) = 1 + size l`. My smt hint failed — likely a wrong lemma name. Let me verify the exact name in the EasyCrypt stdlib.

`size_cons` doesn't exist — `size` is defined recursively (`size (y::ys) = 1 + size ys`), so the earlier failure was an unknown-symbol abort, not a real smt failure. Let me retry with only the valid lemma.
