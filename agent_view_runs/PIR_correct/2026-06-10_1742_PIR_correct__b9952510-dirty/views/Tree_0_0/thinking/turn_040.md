# Tree-0.0 · turn 40 · probe_tactic

<!-- session 61c51f31-dc55-4d83-a89a-cd3ee77df49c · 2026-06-11T01:06:46.434Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite /predT in H; split.`

---

Every chain ending in smt is reported as "no progress" — meaning smt itself is failing, not a syntax issue. The `predT`-in-`H` vs `fun _ => true`-in-goal split is the prime suspect. Let me isolate whether `rewrite /predT in H` even works by probing it alone.
