# Tree-0.0 · turn 24 · commit_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:05:55.284Z -->

**Intent:** `commit_tactic`  
**Payload:** `have f_eq : equiv[DoubleQuery(PRFi).f ~ DoubleQuery(Sample).f : (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => ={arg} /\ ={DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1}) ==> (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => ={res} /\ ={DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1})].`

---

The `have f_eq` statement parses and type-checks. Committing it.
