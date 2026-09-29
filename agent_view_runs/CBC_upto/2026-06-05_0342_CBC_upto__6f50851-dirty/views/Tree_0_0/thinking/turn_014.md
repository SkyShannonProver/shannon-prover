# Tree-0.0 · turn 14 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T10:53:59.793Z -->

**Intent:** `probe_tactic`  
**Payload:** `byequiv: DoubleQuery.bad => //=.`

---

EC definitively rejects byequiv on the abs-difference goal ("invalid goal shape"). I need the manual upto-bad reduction. Rather than guess the arithmetic plumbing, let me read how EasyCrypt's own theory library concludes the switching lemma (same abs-diff upto-bad shape). Let me find the EC source.

Found it — line 448 uses `byequiv: PRP_indirect_bad.bad=> //=` — the colon form passing the bad event. Let me read that context.

This is the exact template. The concluding tactic is the colon form `byequiv: BAD_EVENT => //=; 2:by smt().` followed by `proc; call (_: bad, inv, inv')`. The bad flag is tracked on the `{1}` side and linked to the `{2}`-side bound event via the call invariant. Let me probe this form on my goal to see the subgoals EC generates.
