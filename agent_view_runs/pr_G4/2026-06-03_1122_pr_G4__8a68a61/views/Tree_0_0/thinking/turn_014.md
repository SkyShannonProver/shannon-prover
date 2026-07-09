# Tree-0.0 · turn 14 · probe_tactic

<!-- session b9b6df1c-2d45-4f29-b7d5-cce4da2b9fcc · 2026-06-03T18:39:21.387Z -->

**Intent:** `probe_tactic`  
**Payload:** `seq 13 : (size G3.cilog <= size G1.log /\ size G1.log <= PKE_.qD).`

---

Now the focused goal is the hoare side-goal `hoare[1..21 : true ==> size G3.cilog <= qD]`. I'll track the joint invariant `size cilog <= size log <= qD` (the oracle's guard is on `log`, and `cilog` grows in lockstep with `log`). Since this is a hoare goal with no probability budget, `seq` should be fine. Let me probe.
