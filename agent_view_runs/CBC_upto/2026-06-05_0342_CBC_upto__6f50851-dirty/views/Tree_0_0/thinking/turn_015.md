# Tree-0.0 · turn 15 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T10:54:29.798Z -->

**Intent:** `probe_tactic`  
**Payload:** `byequiv: DoubleQuery.bad => //=; 2: by smt().`

---

`byequiv: DoubleQuery.bad => //=` is accepted by EC. Let me read the post-probe goal structure.

`byequiv: DoubleQuery.bad => //=` yields 2 goals: **Goal 1** the upto-bad equiv `INDR_CPA_direct(CBC_Oracle(DoubleQuery(PRFi)),A).main ~ ...(DoubleQuery(Sample))... : ={glob A} ==> (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => res{1}=res{2})`, and **Goal 2** the numeric side (template closes with `2:by smt()`). Let me probe the combined form to confirm `2:by smt()` discharges goal 2, leaving just the equiv.
