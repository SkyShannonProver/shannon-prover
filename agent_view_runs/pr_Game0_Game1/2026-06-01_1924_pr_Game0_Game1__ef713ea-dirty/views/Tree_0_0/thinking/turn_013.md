# Tree-0.0 · turn 13 · undo_to_checkpoint

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:49:37.403Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `(none)`

---

The `call` was accepted! And it generated the oracle subgoal for `Log(LRO).o`:

```
pre =
  arg{1} = arg{2} /\
  Log.qs{1} = Log.qs{2} /\ eq_except (pred1 Game1.r{2}) LRO.m{1} LRO.m{2}

    Log(LRO).o ~ Log(LRO).o 


```

Now I need to verify that `Log(LRO).o` maintains the `eq_except` invariant while also ensuring the results match. The problem is that when `arg` equals `Game1.r{2}`, the LRO maps diverge at that point, causing the oracle to return different values and breaking the `res{1} = res{2}` requirement.

Looking at how `Log(LRO).o(x)` executes: it appends `x` to the query sequence (which stays consistent across both sides), then calls the underlying `LRO.o(x)`. When `x` is already in the map, it returns the stored value; otherwise it samples fresh. For any `x` different from `Game1.r{2}`, the `eq_except` invariant guarantees the maps agree at that key, so both sides return the same stored value. But I need to verify whether `eq_except` actually ensures the domains match—that is, whether a key exists in one map if and only if it exists in the other. m1.[x] = m2.[x]`. Since `.[]` returns `None` for undefined keys, this also means `x ∈ dom(m1) iff x ∈ dom(m2)` for `x ≠ r`.
- So if `x ∉ dom(LRO.m{1})` (and `∉ dom(LRO.m{2})`): both sample fresh. I couple them with `rnd`. `res{1} = res{2}`. ✓
- If `x ∈ dom(LRO.m{1})` (and `∈ dom(LRO.m{2})`): both return `oget m.[x]`. Since `m{1}.[x] = m{2}.[x]`, `res{1} = res{2}`. ✓
- `eq_except` is preserved (updated at `x ≠ r`). ✓

When `x = Game1.r{2}`, the left oracle has `Game1.r` stored from encryption but the right might not, so they diverge—left returns the cached value while right samples fresh, making `res{1} ≠ res{2}`. This means the oracle subgoal is actually unprovable for this case, which confirms my suspicion. But I'm puzzled because the `call` was accepted and generated this subgoal in the first place.

Let me reconsider whether the subgoal could still be proved with a case split on `x = Game1.r{2}`, or if I need to abandon this invariant entirely and try something different. Actually, I should think more carefully about what `eq_except (pred1 Game1.r{2})` really constrains about the domains—specifically whether `Game1.r{2}` must be in both maps or neither.

The definition says that for all `x ≠ Game1.r{2}`, the maps agree on `x`, but it says nothing about what happens at `Game1.r{2}` itself. So in the oracle call with `x = Game1.r{2}`, the left map could have `Some r0{1}` while the right map has `None`, which would cause the responses to differ and make the subgoal unprovable.

The real problem only surfaces in the "good" case where `Game1.r` wasn't queried — that's when the maps actually diverge at this key. I need a stronger invariant that accounts for this difference, or I need to reconsider how the maps should be constructed.

If I add the constraint that `Game1.r{2}` stays out of the right map's domain, then the left side returns a stored value while the right samples fresh. Both values come from the same distribution, but they're sampled at different times and aren't coupled together, so I can't guarantee they're equal.

The real issue is that the left's value was fixed during encryption and can't be retroactively matched to a fresh sample on the right. This means the standard invariant-based approach fundamentally won't work here.

I need to try a different strategy entirely. Let me explore using `eager` to defer the map update, or go back further with `undo_to_checkpoint` and attempt the `byequiv ... : bad` form with different syntax.

Actually, I should reconsider how `byequiv` works in EasyCrypt. The bad event needs to be expressible on both sides, but `Game1.r` only exists on the right side in my setup. That's probably why the tactic rejected it — the bad event can't be formulated symmetrically across both games.

Looking at how the standard BR93 proof handles this, I think the solution is to introduce an intermediate module that mirrors `BR93_CPA(A)` but also tracks the challenge randomness `r`. Then I can show the original game equals this intermediate one, and use `byequiv ... : bad` to relate the intermediate game to `Game1` where the bad event is now expressible on both sides since both track `r`. Game1's `main` procedure actually differs from BR93_CPA(A)'s in two distinct ways: it introduces a module variable `r` to track the challenge randomness, and it replaces the LRO.o call with a fresh sample. I'm wondering if there's an intermediate game that only applies the first change—adding the `r` variable—while still using LRO.o, which would help bridge the proof between the two games.

Looking back at the file, Game1 seems to apply both changes simultaneously with its `with` syntax, so there's no intermediate step available. Maybe I don't actually need one though—perhaps I can prove this differently without relying on `byequiv ... : bad`. Let me try a completely different approach using `byphoare` instead, though I'm skeptical since `byphoare (_ : true ==> res)` would just bound the probability by 1, which isn't useful. I'm also considering whether `phoare` might work better here for reasoning about probabilistic properties.

Actually, let me step back and try the `byequiv` approach again with a cleaner form, using `mem` instead of the `\in` operator to avoid potential parsing issues with escaping.

The real issue is that for `byequiv` to work with the bad event pattern, my goal needs to match a specific structure where the second probability is split into a base case plus the bad event probability. Let me reconsider what the original goal actually requires before I introduced the `have` statement.

Looking at the pattern more carefully, when I use `byequiv ... : F` to specify a bad event, EasyCrypt generates a pRHL obligation that needs to prove equivalence on the left side when the bad event doesn't occur on the right. The problem is that my bad event `Game1.r \in Log.qs` references a state variable that only exists in the right module, so there's no corresponding left-side version of this event—which breaks the equivalence proof structure. evaluates `F` on side 2.

Actually, that's what should happen. The bad event `F` is evaluated on the right side (c2's final state). So `F{2} = Game1.r{2} \in Log.qs{2}`. On the left side, there's no `Game1.r`, but that's fine because `F` is only evaluated on side 2.

So the pRHL obligation should be:
```
{Pre} BR93_CPA(A).main ~ Game1.main {!(Game1.r{2} \in Log.qs{2}) => res{1} = res{2}}
```

And maybe an additional condition about the bad event being well-defined.

If this is what EasyCrypt generates, it should be fine. The issue might be syntactic — maybe the `byequiv ... : F` annotation expects `F` to be a simple predicate rather than a complex expression. Let me try using `mem` instead of the membership operator, or maybe removing the parentheses around the expression. But I'm deep in the proof already with multiple tactics applied, so undoing all the way back would lose significant progress. I should try to make the current approach work instead. Writing disjunctive invariant logic...

The postcondition needs to be the invariant conjoined with `={res}`, which distributes the disjunction but still requires `={res}` in both branches—and that fails in the bad case where `Game1.r{2} \in Log.qs{2}`. I'm realizing that EasyCrypt's `call` tactic fundamentally requires `={res}` for oracle methods, so I can't bypass this constraint directly. But there has to be a way to handle "up to bad" reasoning for oracles in cryptographic proofs, and I'm wondering if `byequiv` with a bad event might be the mechanism that lets me work around this.

The `byequiv ... : bad` form could generate different oracle subgoals that don't enforce `={res}` in the bad case, which would explain why it exists as a separate tactic rather than just being a manual decomposition. I should go back to the original goal and try `byequiv ... : bad` with the right syntax instead of trying to decompose it manually.
