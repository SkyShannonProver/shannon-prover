# Tree-0.0 · turn 53 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:22:07.121Z -->

**Intent:** `probe_tactic`  
**Payload:** `seq 3 3 : (={i, p} /\ 0 <= i{1} <= size p{1} /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => c{1} = c{2} /\ s{1} = s{2} /\ DoubleQuery.qs{1} = DoubleQuery.qs{2} /\ fdom PRFi.m{1} = DoubleQuery.qs{1})).`

---

The enc body is exposed and `f_eq` is callable. Let me set up the loop: `seq 3 3` to couple the initial sample and establish the bad-conditional while invariant. Probing it.
