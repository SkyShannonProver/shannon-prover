# Tree-0.0 · turn 2 · commit_tactic

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:28:11.205Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv (_ : ={glob A, glob LRO, glob Log} ==> !(Game1.r \in Log.qs){2} => ={res}) : (Game1.r \in Log.qs).`

---

The tactic was rejected. Let me read the full workspace view to get the error details.

The error message doesn't give me the specific EasyCrypt error. The tactic was rejected. Let me think about what might be wrong.

Possible issues:
1. The `byequiv` with failure event syntax might be wrong
2. The `=> //.` might be closing goals that can't be closed trivially
3. The glob expressions might be wrong

Let me try a different approach. Maybe I should use a simpler `byequiv` without the `=> //.` to see what goals are generated. Or maybe I should try a different tactic altogether.

Actually, let me reconsider. In EasyCrypt, the `byequiv` with failure event for proving `Pr[G0:E] <= Pr[G1:E] + Pr[G1:F]` might need a slightly different syntax. 

Let me test a simpler version without the `=> //.` to see what subgoals actually appear, or maybe I need to restructure the whole approach and look more carefully at how Game1 is defined in the target file.

Now I'm seeing that Game1 is constructed as a module modification of BR93_CPA(A), where it introduces a local random variable and inlines the key generation and challenge encryption steps to idealize the RO call.

The critical insight is that instead of obtaining `h` through the random oracle at the challenge nonce `r`, Game1 samples `h` fresh from the plaintext distribution. The `byequiv` argument hinges on the fact that when the adversary never queries `r` to the lazy RO, it returns a fresh sample anyway, making the two games indistinguishable in that case.

I'm trying to figure out the right `byequiv` syntax for this. I suspect the issue is that `byequiv` might not directly handle goals with the `+ Pr[...]` form, so I may need to decompose the goal first using a lemma or tactic. In EasyCrypt, there should be a specific approach for the fundamental lemma of game playing—possibly using `byequiv` in "upto-bad" mode to prove bounds of the form `Pr[G1:E] <= Pr[G2:E] + Pr[G2:F]`.

The syntax I'm trying involves specifying the precondition, postcondition, and the bad event, but I'm running into issues with how the escape characters are being processed in the JSON payload. The `\in` operator for membership needs careful handling depending on the context. I'm checking the JSON encoding—`\\in` in JSON becomes `\in` in the actual string, which is what EasyCrypt needs for the membership operator. The manager output confirms this is correct. But something else must be causing the issue, so let me try removing the `=> //.` to see what subgoals actually remain unsolved, or reconsider whether the `byequiv` syntax with failure events matches this version of EasyCrypt's expectations. I'm reconsidering the approach—maybe I should decompose the probability using a union bound first, showing that `Pr[G0:E] <= Pr[G0:E /\ !bad] + Pr[G0:bad]`, then use `byequiv` to establish equivalence on the constrained event, and finally combine the pieces. Let me explore whether EasyCrypt has a built-in lemma for this fundamental decomposition, or if I need to manually construct it. I'm working through the syntax for EasyCrypt's `byequiv` tactic when proving inequality goals with a "upto bad" argument. The postcondition needs to express that either the results match or the bad event occurred on the right-hand side, and I'm trying different formulations to get the syntax right for this kind of proof. I'm realizing the core issue: `Game1.r` exists only in the `Game1` context, so I can't reference it directly within `BR93_CPA(A)`'s event. The right approach here is to use EasyCrypt's `byequiv` with the "upto bad" technique, where the bad event `Game1.r \in Log.qs` only applies to the right-hand game.

I'm trying to formulate the correct syntax for this equivalence proof, exploring whether to use the infix notation `Game1.r \in Log.qs` or the prefix form `mem Log.qs Game1.r` since they're equivalent in EasyCrypt.

Writing the byequiv statement...

The real issue might be that the `=> //.` at the end is causing the tactic to fail—it's trying to solve remaining goals trivially, but if any goal can't be solved that way, the whole tactic gets rejected. Let me reconsider what's actually wrong with the tactic syntax itself rather than assuming the subgoals are the problem.

I'm wondering if the `byequiv` syntax for upto-bad reasoning needs a different structure—maybe specifying the bad event and postconditions in a particular way that EasyCrypt expects, like separating the equivalence precondition from the bad event condition or using a different annotation format altogether.

The real issue is that the bad event `F = Game1.r \in Log.qs` only exists in `Game1`, not in `BR93_CPA(A)`, so `F{1}` doesn't have a meaningful interpretation on the left side. This means I can't use a standard `byequiv` to express the upto-bad bound directly—I need either a coupling that tracks the bad event only on the right side, or I need to introduce an auxiliary variable on the left side to make the bad event expressible on both sides.

Trying a one-sided bad event syntax where the bad condition is only interpreted on side 2, then attempting to write the tactic without the `=> //.` suffix that was causing the rejection.

The real issue is that `byequiv` itself is being rejected, not the subsequent tactic script. I'm reconsidering whether `glob` expressions are valid here — `A` is declared as a module in the section, so `glob A` should work, but I need to check if `Game1`'s own globals need to be accounted for in the precondition.

Looking more carefully at the `with` syntax used to define `Game1`, I'm questioning whether this particular EasyCrypt syntax is even standard.  The inline module modification might have specific implications for how `byequiv` handles it. Let me try a more manual approach instead—either inlining the modules to show equivalence directly, or building up the proof with a chain of intermediate steps. I could also try using probability reasoning first, rewriting the goal `Pr[G0:E] <= Pr[G1:E] + Pr[G1:F]` by decomposing the RHS into disjoint events.

Actually, this decomposition approach is getting messy. Let me just attempt `byequiv` without the `with` modifier and see if that works.

The real issue is that the bad event `Game1.r \in Log.qs` references a variable that only exists in `Game1`, not in `BR93_CPA(A)`, so I can't directly split the probability. I need to either leverage EasyCrypt's built-in "upto bad" mechanism for one-sided bad events, or construct an intermediate game that mirrors `BR93_CPA(A)` but includes the necessary variable.

Looking at the actual definitions, `Game1` already tracks `r`, and the only substantive difference from `BR93_CPA(A)` is that it samples from the ideal distribution instead of querying the LRO. These games are indistinguishable as long as `r` hasn't been queried to the LRO or exposed through the adversary's queries. I should check the exact game definitions in the source to figure out whether `eager`, `phoare`, or another tactic would work best here. The `with` override syntax is a legitimate EasyCrypt feature for defining game variants. For the "upto bad" approach, I need to use the `byequiv` tactic with the right form—it should take a precondition and a failure event, allowing me to prove the probability bound by relating the two games up to when a distinguishing event occurs.

Let me try a different strategy: I'll use intermediate inequalities with `have` statements to decompose the probability into pieces I can handle separately, breaking down the main game's success probability in terms of the variant game and the bad event. Writing proof tactics... I'm realizing the JSON encoding might be the culprit here—`\in` needs to be escaped as `\\in` in the JSON payload, but I should verify that the MCP tool isn't double-escaping it on its end.
