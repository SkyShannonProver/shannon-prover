# Tree-0.0 · turn 45 · probe_tactic

<!-- session 61c51f31-dc55-4d83-a89a-cd3ee77df49c · 2026-06-11T01:07:33.069Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite /predT in H; smt(BBS.big_cons xorwA xorwC xorw0 xorwK).`

---

Now the symmetric case (`!v`, so `j::s'`). H is back in predT form for this branch. Same recipe — let me probe whether the predT-unfold plus smt closes the whole conjunction in one shot this time.
