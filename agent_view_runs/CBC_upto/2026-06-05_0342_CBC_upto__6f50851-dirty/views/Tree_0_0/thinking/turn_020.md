# Tree-0.0 · turn 20 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T10:58:29.134Z -->

**Intent:** `probe_tactic`  
**Payload:** `call (_: DoubleQuery.bad, ={DoubleQuery.qs} /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ fdom PRFi.m{1} = DoubleQuery.qs{1}, DoubleQuery.bad{1} <=> DoubleQuery.bad{2}).`

---

The `call` upto-bad form follows the template `call (_: BAD, GOOD_REL_INV, BAD_LINK_INV)`. Note from the docs: do NOT include `={glob A}` (EC handles it implicitly). The adversary calls `enc` (which loops calling `DoubleQuery(F).f`), so the good invariant must link `fdom PRFi.m{1}` to `DoubleQuery.qs`. Let me probe the call to see the generated subgoals.
