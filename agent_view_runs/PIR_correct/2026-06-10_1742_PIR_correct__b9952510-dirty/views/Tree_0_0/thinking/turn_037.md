# Tree-0.0 · turn 37 · probe_tactic

<!-- session 61c51f31-dc55-4d83-a89a-cd3ee77df49c · 2026-06-11T01:00:34.453Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite /predT in H; smt(BBS.big_cons xorwA xorwC xorw0 xorwK).`

---

`big_cons` as a standalone rewrite keeps the same operator set, so the no-op detector reverts it — I must close the leaf in one shot. The key is whether smt can do the abelian-group step once `predT` in `H` matches the goal's `fun _ => true`. Let me probe that combined form and read the actual verdict.
