# Tree-0.0 · turn 39 · probe_tactic

<!-- session 61c51f31-dc55-4d83-a89a-cd3ee77df49c · 2026-06-11T01:05:02.298Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite -/predT; smt(BBS.big_cons xorwA xorwC xorw0 xorwK).`

---

`big_cons` does match (`big P F (x::s) = if P x then F x +^ big P F s else big P F s`). The recurring blocker is the `predT` (in `H`) vs `fun _ => true` (in the goal, from an earlier `rewrite /predT /=`) mismatch that stops smt from connecting `H`. Let me try folding the goal back to `predT` so everything is uniform, then close — in one chain so it's accepted only if it closes.
