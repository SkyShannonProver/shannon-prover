# Tree-0.0 · turn 67 · commit_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:12:52.337Z -->

**Intent:** `commit_tactic`  
**Payload:** `skip.`

---

Now I have the pure relational implication. Committing `skip`, then I'll prove it: initial invariant (i=0, `take 0 ns = []` ⇒ vacuous), termination (arithmetic), and exit (i_R=size ⇒ `take (size ns) ns = ns`, and `c.\`1 \in ns` via `mem_undup`).
