# Tree-0.0 · turn 2 · probe_tactic

<!-- session 2e75d736-140d-4a8e-9742-884a1444224e · 2026-06-01T06:56:06.116Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> h1 h2; rewrite eq_iff; split => [/fsetP heq | ->] //; apply fsetP => x; have := heq x; rewrite !in_fsetU !in_fset1; smt(nin_is_restr).`

---

The fast-track probe failed with "cannot find lemma `is_restrS'". The lemma `is_restrS` is defined in the file but EasyCrypt can't find it by that name. This might be because `is_restrS` is defined after `is_restr_Ueq` in the file, so it's not available yet. Let me check the file structure...

Looking at the file, the order is:
1. `restrS`


2. `nin_is_restr`
3. `is_restr_diff`
4. `is_restr_Ueq` ← we are here
5. `is_restr_addS`
6. `is_restrS`
7. `is_restr_restr`
8. `is_restr_fset0`
9. `restr_0`

So `is_restrS` and `is_restr_addS` are defined after `is_restr_Ueq`, which means they're not available at this proof point. Only the lemmas before it—`restrS`, `nin_is_restr`, and `is_restr_diff`—can be used here.

For the goal, I need to show that if `n ∉ s1` and `n ∉ s2`, then `{n} ∪ s1 = {n} ∪ s2` if and only if `s1 = s2`. The backward direction is immediate by substitution, and for the forward direction, I can use the fact that `n` is not in either set to cancel it out from both sides of the union. Writing proof tactics... Finishing the proof approach...

Since `n` is not in either `s1` or `s2`, when `x = n` both sides of the equality are true, and when `x ≠ n` it reduces to comparing membership in `s1` versus `s2`. I'm setting up a tactic proof that applies set extensionality and uses the membership lemmas to handle the disjunction, then letting the SMT solver finish with the constraints from the hypotheses. Testing different proof strategies...
