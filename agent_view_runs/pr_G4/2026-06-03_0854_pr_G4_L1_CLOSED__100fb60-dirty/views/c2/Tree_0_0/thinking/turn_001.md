# Tree-0.0 · turn 1 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T16:55:52.823Z -->

**Intent:** `commit_tactic`  
**Payload:** `hoare.`

---

I'll start by loading the proof intent tool and reviewing the current state.

This is the "fail" branch of a `seq` split with bound `[<=] 0%r`. The post requires the conjunction `(g^u ∈ map.1) ∧ (g_^u' ∈ map.2) ∧ size≤qD ∧ w≠0 ∧ g_=g^w` (plus the new `r'`/`r` facts), but the precondition is the *negation* of exactly that conjunction, and sampling `r'`/`r` doesn't touch any of those variables. So the post is impossible — probability 0.

The clean route: reduce the `≤ 0%r` phoare to a `hoare` judgment with negated post, then discharge.
