# Tree-0.0 · turn 4 · commit_tactic

<!-- session 420ddf0e-a769-49f3-83cb-e3b3c3d9112b · 2026-06-03T16:03:10.494Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ll_dec : islossless G4.O.dec by islossless.`

---

The seq produced 5 goals. The current one shows `post = true` with no visible bound — let me read the full view to understand exactly what each subgoal requires.

The seq's upper-bound rule produced 5 goals; this first one (code 1–21, `post = true`) is the **losslessness obligation** `phoare[c1 : true ==> true] = 1%r` for the prefix. I need the prefix to terminate with probability 1, which requires `A.choose` lossless (via `choose_ll`) and the dec oracle lossless. Let me first establish the oracle losslessness fact.
