# Tree-0.0 · turn 62 · commit_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:38:01.077Z -->

**Intent:** `commit_tactic`  
**Payload:** `have f_eqM : forall (B : bool), equiv[DoubleQuery(PRFi).f ~ DoubleQuery(Sample).f : DoubleQuery.bad{2} = B /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => arg{1} = arg{2} /\ DoubleQuery.qs{1} = DoubleQuery.qs{2} /\ fdom PRFi.m{1} = DoubleQuery.qs{1}) ==> (B => DoubleQuery.bad{2}) /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => res{1} = res{2} /\ DoubleQuery.qs{1} = DoubleQuery.qs{2} /\ fdom PRFi.m{1} = DoubleQuery.qs{1})].`

---

The `f_eqM` statement parses. Committing it, then I'll prove it from `f_eq` + a side-2 monotonicity hoare via `conseq`.
