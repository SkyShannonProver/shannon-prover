# Tree-0.0 · turn 61 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:37:50.561Z -->

**Intent:** `probe_tactic`  
**Payload:** `have f_eqM : forall (B : bool), equiv[DoubleQuery(PRFi).f ~ DoubleQuery(Sample).f : DoubleQuery.bad{2} = B /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => arg{1} = arg{2} /\ DoubleQuery.qs{1} = DoubleQuery.qs{2} /\ fdom PRFi.m{1} = DoubleQuery.qs{1}) ==> (B => DoubleQuery.bad{2}) /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => res{1} = res{2} /\ DoubleQuery.qs{1} = DoubleQuery.qs{2} /\ fdom PRFi.m{1} = DoubleQuery.qs{1})].`

---

Back at the loop body. Let me build a monotonicity-strengthened `f_eqM` (with ghost `B` capturing pre-call `bad{2}`, adding `B => bad{2}` to the post). Probing the statement first.
