# Tree-0.0 · turn 107 · commit_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:51:46.255Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> z; inline*; auto.`

---

`if` hit "invalid first instruction" — the head after `inline*; sp` differs. Let me commit `move=> z; inline*; auto` and inspect the residual, as I did for side-1.
