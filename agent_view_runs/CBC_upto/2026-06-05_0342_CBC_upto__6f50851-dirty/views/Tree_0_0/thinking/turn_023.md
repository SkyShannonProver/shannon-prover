# Tree-0.0 · turn 23 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:05:47.701Z -->

**Intent:** `probe_tactic`  
**Payload:** `have f_eq : equiv[DoubleQuery(PRFi).f ~ DoubleQuery(Sample).f : (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => ={arg} /\ ={DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1}) ==> (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => ={res} /\ ={DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1})].`

---

Goal 2/4 is the substantive enc good-case equiv (with a bad-conditional post). This is the crux: `CBC_Oracle(DoubleQuery(PRFi)).enc ~ CBC_Oracle(DoubleQuery(Sample)).enc` with a while-loop that calls the bad-tracking `f`. Before diving into the loop/nested-upto-bad construction, let me validate my plan with the advisor.

Advisor validates the route and gives the refined plan: factor `f` into an `f_eq` equiv lemma (isolating the asymmetric-sampling hazard at the bad-flip), then the loop body becomes `sp; wp; call f_eq; auto`. Let me first probe the `have f_eq : equiv[...]` statement to confirm it parses well-formed.
