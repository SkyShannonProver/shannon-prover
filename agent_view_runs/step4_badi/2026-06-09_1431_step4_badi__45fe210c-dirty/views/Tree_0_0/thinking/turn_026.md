# Tree-0.0 · turn 26 · commit_tactic

<!-- session 89741c4d-97d4-4e85-92cf-0be265f01f88 · 2026-06-09T21:56:55.052Z -->

**Intent:** `commit_tactic`  
**Payload:** `smt(neq_w1_w2).`

---

smt can't see why `w1 <> w2`. Checking how `w1`/`w2` are declared in the source file.

It's a section axiom: `neq_w1_w2 : w1 <> w2` (line 1864). Passing it to smt explicitly.
