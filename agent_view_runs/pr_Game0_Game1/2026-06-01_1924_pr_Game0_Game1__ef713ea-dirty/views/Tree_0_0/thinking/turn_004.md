# Tree-0.0 · turn 4 · commit_tactic

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:32:29.778Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv (_ : ={glob A, glob LRO, glob Log} ==> res{1} => (res{2} \/ (Game1.r{2} \in Log.qs{2}))).`

---

The `have` was accepted and now I have 2 goals. The first goal is:

```
Pr[BR93_CPA(A).main() @ &m : res] <=
Pr[Game1.main() @ &m : res \/ (Game1.r \in Log.qs)]
```

This is a `<=` between two `Pr` terms. I can prove this with `byequiv` where the postcondition is an implication `res{1} => (res \/ Game1.r \in Log.qs){2}`.


The two games only diverge at the encryption step—`BR93_CPA(A)` queries the lazy random oracle while `Game1` samples directly from the plaintext distribution. When the adversary hasn't queried the challenge through the oracle, both games produce identical results since the lazy RO would return a fresh sample anyway. If the adversary has queried it, the bad event triggers, so the coupling argument works.

Now I'm setting up the equivalence proof: if the adversary wins in the first game, then either they also win in the second game or the bad event occurs. I'll use an equivalence tactic with a postcondition that captures this disjunction, being careful about how the return values are referenced in EasyCrypt's probability framework. I'm working through the syntax for the EasyCrypt tactic, trying to figure out whether to use `\/` or `||` for disjunction in the postcondition, and dealing with potential parsing ambiguities around how the implication chains together. I'm realizing that in EasyCrypt's pRHL, the `{2}` tag applies to individual variables rather than entire expressions, so I need to separate the disjunction and tag each component independently as `res{2} \/ (Game1.r \in Log.qs){2}`. I'm working through the operator precedence issue with the `\in` operator in EasyCrypt—I need to add parentheses around `(res{2} \/ (Game1.r{2} \in Log.qs{2}))` to ensure the membership test is evaluated before the disjunction.
