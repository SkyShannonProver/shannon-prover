# Tree-0.0 · turn 14 · undo_to_checkpoint

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:52:27.613Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `{"checkpoint_id": "cp_9_02d6368229aa15c2"}`

---

Good, I can see the checkpoint menu. I need to go back much further. The fundamental issue is that `call (_ : Inv)` requires `={res}` for oracle methods, which doesn't work for "up to bad" reasoning. I need to restart from the beginning with a different approach.

Let me go back to before the `have` — I need to restart the entire proof. Looking at the checkpoints, the earliest available is "before committed tactic #3" (`proc.`), which is inside the `byequiv` from the `have` subgoal. But I need to go further back — before the `have` itself.

Wait, checkpoint #3 is `proc.` which was committed as tactic #3. 

The checkpoints only go back to tactic #3, but I need to rewind past the `have` statement that came first, and the `byequiv` that followed it. Let me try using `fresh_restart` to begin completely from scratch instead.

Actually, I realize `fresh_restart` will erase the entire committed branch, so that's the right move here. Before I do that though, let me think through my strategy.

The core issue is that standard `call (_ : Inv)` requires `={res}` for oracle methods, which breaks down in "up to bad" reasoning where the oracle returns different values when the bad event triggers. The solution in EasyCrypt is to use `byequiv` with the `: bad` annotation at the top level—this generates different proof obligations that don't enforce `={res}` for the oracle in the bad case. My earlier attempts at this syntax were rejected, so I need to reconsider the parsing.

Looking back at the original goal, it matches the pattern for `byequiv ... : bad` perfectly: I have `Pr[BR93_CPA(A).main() @ &m : res] <= Pr[Game1.main() @ &m : res] + Pr[Game1.main() @ &m : Game1.r \in Log.qs]`, which fits the form `Pr[c1:E] <= Pr[c2:E] + Pr[c2:F]`. So the tactic should work if I get the syntax right.

The issue is that my attempts with `byequiv (_ : ={glob A, glob LRO, glob Log} ==> ={res}) : (Game1.r \in Log.qs).` keep getting rejected, even when I try providing the postcondition explicitly as `!bad => ={res}`. Let me verify whether this is a version compatibility issue or something else with how EasyCrypt is set up.

Actually, I think I've found the real problem: `byequiv ... : bad` requires the bad event to be expressible on both sides of the coupling, but `Game1.r` only exists in `Game1`, not in `BR93_CPA(A)`. So I need to either introduce an auxiliary variable on the left to track `r`, or find another approach.

Since I can't modify `BR93_CPA(A)` directly, I could define an intermediate game that's identical to `BR93_CPA(A)` but also records the challenge randomness, then show the probability bounds using that auxiliary game. But that's complex in EasyCrypt. Let me look more carefully at how `Game1` is actually defined relative to `BR93_CPA(A)` to see if there's a simpler path forward. I see that the `with` syntax lets me replace specific procedure calls within the original game—the `^ <@ {2}` notation targets the second `<@` operation in the original `main`, which is the key generation step, and then `~ { ... }` provides the replacement code. Game1 essentially takes BR93_CPA(A)'s main and swaps out certain operations, while introducing `r` as a module-level variable that gets assigned during the encryption replacement. I'm wondering if EasyCrypt has built-in support for reasoning about these `with` modifications through `byequiv`, or if I need to pivot to a different proof strategy altogether—though the `have` approach I've already developed seems promising as a foundation.

I've managed to establish the inequality using `byequiv` with a postcondition that allows the right side to satisfy either the original condition or the bad event, but now the real challenge is proving the pRHL judgment itself. The crux is handling the oracle call in the suffix where the left side encrypts with LRO.o(r) while the right uses fresh randomness, followed by both invoking the adversary. Rather than relying on `call` for the adversary invocation, I could try using `conseq` to relax the postcondition to something more tractable—specifically, I might strengthen the precondition or weaken what I'm trying to prove about the final state.

Let me explore whether I can use the `eager` tactic to restructure the left program around the LRO oracle call. I'm wondering if there's a simpler approach I'm overlooking, so let me revisit how BR93 handles this in EasyCrypt. I should check the ROM theory file for relevant lemmas about lazy random oracles and the "up to bad" technique that might help with this transformation. can use.

But I can actually look at the local files! Let me search through the EasyCrypt theories for relevant lemmas about "upto" or "eager" that might help here.

I should be strategic about this—let me look for `upto` or `bad` tactic support in the local EasyCrypt installation, since the cross-file references point to `easycrypt-src/theories/crypto/ROM.eca`.

Actually, let me refocus on making progress with the proof itself. What if I try a different approach entirely and skip `byequiv` for this subgoal, using a probability argument instead?

The key insight is that I could prove the inequality by using `byequiv` with a postcondition that tracks the oracle difference through the relational assertion—something like establishing that if the first game produces a result, then either the second game does too or the game1 random value ends up in the log. I've been stuck on whether the `call` tactic requires `={res}` for the oracle postcondition, but I keep hitting the same wall. Let me step back and try a completely different approach using eager reasoning instead.

The idea is to transform the left game so that the LRO query during encryption gets replaced with a fresh sample, and then defer the map update until the adversary actually queries that point. Once I do this transformation, the modified left program matches the encryption in Game1, and the only difference is how the oracle handles the deferred update.

The challenge is figuring out the right EasyCrypt tactics to implement this—I'm not confident about the syntax for `eager` or similar transformations. Maybe I should just go back to basics and try `byequiv` directly on the original goal without the intermediate `have` subgoal.

I'm wondering if EasyCrypt can pattern-match a `<=` goal that has a `+` term on the right side, where the second probability represents the bad event. Let me attempt `fresh_restart` followed by a carefully constructed `byequiv` call that specifies the equivalence and the bad event annotation.

The issue might be with how the membership operator `\in` is being escaped in the JSON representation—it needs to be `\\in` to properly produce the backslash. I'm trying different variations of the tactic, first with the full terminator `=> //.`, then without it to see which form the prover accepts.

Now I'm experimenting with stripping back the precondition and postcondition to see if EasyCrypt can infer them automatically—trying just the bad event alone, or with trivial pre/postconditions, or removing the implication operator entirely to find the minimal syntax that works. I'm considering splitting the postcondition into two cases: one where the bad event holds (trivially satisfied), and another where it doesn't, which would require showing the oracle behaves identically on both sides when the adversary hasn't queried the result.

The challenge is that EasyCrypt's `case` tactic operates on preconditions, not postconditions, so I'd need to use `conseq` to reformulate the postcondition as a disjunction that captures both scenarios—either the bad event occurs or the outputs match across both games.

But this still doesn't solve the core problem: how to handle the `call` instruction when the oracle states differ between the two games. I'm realizing that if I set the `call` invariant to `true`, the oracle subgoal becomes much simpler—both sides receive identical inputs and should produce identical outputs—except the global state (the log) might diverge, which breaks the equality assumption I need.

The fundamental issue is that the oracle reads from the global state, and since `LRO.m` differs between the two sides, the oracle can produce different results even with the same input. So the postcondition equality fails no matter what.

Maybe I need to abandon the relational approach entirely and instead use a probabilistic bound like `byphoare` or `phoare` to reason about the probability rather than trying to prove exact equivalence.

Actually, let me shift tactics completely. Instead of proving the probability of `res` is equal, what if I prove that the probability of `res` and `!bad_proxy` in G0 equals the probability of `res` and `!bad` in G1, where `bad_proxy` is the corresponding event in G0 that captures when the oracle's behavior would diverge? The problem is that `bad` in G1 depends on `Game1.r`, which doesn't have a direct counterpart in G0, though `BR93_CPA(A)` does have its own local `r` variable I could use.

The real blocker is that `r` is local to the `enc` procedure, not a module-level variable, so I can't reference it in a probability expression. That's why the standard approach is to introduce a modified G0' that exposes the challenge randomness as a module variable, then show G0 and G0' have the same probability.

Looking at Game1, it's actually making two simultaneous changes to BR93_CPA(A): adding the module variable for `r`, and also replacing the LRO query with direct plaintext sampling. I need to separate these concerns—there should be an intermediate game that only adds the variable storage without changing the sampling behavior yet.

The problem is that no such intermediate game exists in the source file, and I'm not sure if EasyCrypt even allows declaring local modules inside a proof context. Maybe I could use a `have` statement with explicit quantification to introduce this intermediate step, but I'm not certain that would work either.

Let me reconsider whether the `byequiv ... : bad` approach can handle this without an intermediate game. When using `byequiv` with a bad event in EasyCrypt, it typically generates two proof obligations: one showing the programs agree on the result when the bad event doesn't occur, and another relating the bad events across both sides. The challenge is that the bad event might only be expressible on one side of the equivalence, which could make the second obligation impossible to prove or even generate correctly.

Actually, thinking about this more carefully — the mathematical foundation here is that `Pr[G0:res] <= Pr[G1:res] + Pr[G1:bad]` follows from decomposing the first game's success probability into cases where the bad event does or doesn't happen, then using the equivalence to relate those probabilities. This works as long as the bad event has the same probability in both games and the games agree when it doesn't occur.

The issue is that EasyCrypt's `byequiv ... : bad` tactic might require the bad event to exist on both sides to pair them up properly. Since `Game1.r` is only available on the right side after the module extension, the tactic could fail. So I need to think about what alternatives exist — maybe I can structure the games differently, or perhaps the module extension in EasyCrypt actually makes the variable accessible in a way that allows the equivalence to work. and `Game1.main`, it knows that:
- The left module has variables: `glob A`, `LRO.m`, `Log.qs`, etc.
- The right module has: `glob A`, `LRO.m`, `Log.qs`, `Game1.r`, etc.

The extra `Game1.r` on the right is fine — it's just an additional variable that the left doesn't have.

Now, for the `byequiv ... : bad` form where `bad = Game1.r \in Log.qs`:
- On the right: `bad{2} = Game1.r{2} \in Log.qs{2}` — makes sense
- On the left: `bad{1} = ???` — `Game1.r{1}` doesn't exist!

EasyCrypt would need to generate an obligation like `bad{1} => bad{2}`, which requires `bad{1}`. Since `Game1.r` doesn't exist on the left, `bad{1}` can't be formed. But if EasyCrypt only generates a one-sided obligation for `bad{2}` instead, then it avoids this problem entirely — the conclusion becomes `Pr[G0:res] <= Pr[G1:res \/ bad]` rather than needing to bound `Pr[G0:bad']` separately, which is exactly what the `have` subgoal I'm looking at seems to be doing.

The real issue now is proving the pRHL obligation inside the `byequiv`, specifically handling the adversary's `call` when the oracle states differ. I need to find whether EasyCrypt supports a weaker postcondition for the `call` statement that allows the result to diverge or the bad event to occur, rather than requiring strict equality. I need to backtrack and experiment with different `call` syntax variants to find what EasyCrypt accepts, so let me undo to the checkpoint before the current attempt and try a few different formulations.
