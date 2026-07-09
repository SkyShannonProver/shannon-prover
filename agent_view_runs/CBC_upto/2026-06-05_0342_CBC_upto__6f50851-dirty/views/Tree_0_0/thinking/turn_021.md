# Tree-0.0 · turn 21 · commit_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T10:58:48.264Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: DoubleQuery.bad, ={DoubleQuery.qs} /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ fdom PRFi.m{1} = DoubleQuery.qs{1}, DoubleQuery.bad{1} <=> DoubleQuery.bad{2}).`

---

EC accepted the call structure. Let me read the generated subgoals from the probe preview.

The call generates 5 subgoals, exactly mirroring the template: (1) adversary losslessness `forall O, islossless O.enc => islossless A(O).distinguish` (→ `A_distinguish_ll`), (2) the enc good-case equiv (the substantive loop proof), (3,4) bad-side losslessness on each side, (5) init handling. Let me commit the call.
