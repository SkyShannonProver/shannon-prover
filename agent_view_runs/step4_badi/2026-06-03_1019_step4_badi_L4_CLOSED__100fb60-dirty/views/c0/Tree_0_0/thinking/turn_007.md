# Tree-0.0 · turn 7 · inspect_context

<!-- session 7d6b85e1-efc5-4558-ab30-99a9e554877b · 2026-06-03T17:26:37.634Z -->

**Intent:** `inspect_context`  
**Payload:** `call_invariant_skeleton`

---

This is the crux: I must cross the `CPA_game(...).main()` call where the buried abstract adversary `A` calls the oracle whose `set_bad1` differs. I need to understand the wrapper stack (`CPA_game`, `CCA_CPA_Adv`, `BNR_Adv`, `BNR`) to know how deep to inline before reaching `A`. Let me read the sibling `Ske.ec`.

I now understand the structure. The expanded call is:
```
O.init(); CPA_CCA_Orcls(O).init(); BNR(...).init();
b <@ A(BNR(CPA_CCA_Orcls(O))).main()
```
with `O` = `UFCMA_l.O` / `UFCMA_li.O`, differing only in `set_bad1`. I'll cross the buried abstract-adversary call with `call (_: Inv)`. Let me get the mechanical glob frame for the invariant.
