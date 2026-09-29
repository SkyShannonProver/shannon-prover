# Tree-0.1 · turn 12 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:45:15.076Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: (={Log.qs, LRO.m}), ((Game1.r \in Log.qs){2})).`

---

Interesting! Even `call (_: ={Log.qs, LRO.m}, (Game1.r \in Log.qs){2}).` was rejected! But `call (_: true, (Game1.r \in Log.qs){2}).` was accepted. And `call (_: ={glob Log, glob LRO}).` was accepted (without the comma).

So the issue is: `call` with a comma (upto bad) works only when the invariant is `true`? That doesn't make sense.

Wait, let me think about this more carefully. Maybe the issue is with the postcondition/precondition matching. 

I think the problem might be in how the postcondition gets type-checked when I use a non-trivial invariant. The postcondition of the pRHL judgment is something like `(b'{1} = b{1}) = (b'{2} = b{2}) \/ (Game1.r{2} \in Log.qs{2})`, and when the `call` generates goals with the invariant `={Log.qs, LRO.m}`, there's likely a mismatch in how the postcondition gets unified with what the call produces.

Looking at the postcondition structure more carefully, the call should generate `(={b'} /\ inv) \/ bad`, which with the precondition `={b}` should imply the overall goal. But maybe EasyCrypt's `call` tactic for "upto bad" reasoning has stricter requirements—perhaps the invariant can't reference program variables that get modified by the call itself, which would explain why `={Log.qs, LRO.m}` is causing issues.

Actually, I'm realizing that `Log.qs` and `LRO.m` are module variables that the oracle modifies, so the invariant needs to be preserved across oracle calls. Let me think about what goals the `call` tactic actually generated and whether the bad monotonicity or oracle preservation is the real bottleneck here.

When I used `call (_: true, (Game1.r \in Log.qs){2})`, it produced six goals including adversary losslessness, oracle preservation with the invariant, and bad monotonicity goals on both sides. With `true` as the invariant, oracle preservation is trivial, but with `={Log.qs, LRO.m}`, the oracle preservation becomes non-trivial because I need to show the invariant holds after the oracle executes on both sides.

Now I'm realizing the real issue might be with the postcondition itself. For the `call` tactic to work with my invariant and bad event, EasyCrypt needs to derive the postcondition `(b'{1} = b{1}) = (b'{2} = b{2}) \/ (Game1.r{2} \in Log.qs{2})` from the combination of the invariant, the bad event, and the pre-context.

The right disjunct matches the bad event directly, and the left disjunct should follow from the invariant and the fact that `res = b'`, but maybe EasyCrypt's `call` tactic is being stricter about what it accepts. Let me try a different approach with `wp` instead.

Actually, I'm realizing the postcondition is directly about the final state after the `a2` call, not an explicit return statement. The issue might be that I need to handle the return value computation separately before the `call` tactic can work properly. I'm seeing how the postcondition captures both the equality case and the bad event case—when `b'` is set correctly on both sides, the equality holds, but if the adversary triggers the bad event on the right side, that satisfies the disjunction instead.

Let me test whether the issue is with the invariant itself by trying simpler versions, like just tracking `Log.qs` equality or even using `false` as a placeholder invariant to isolate what EasyCrypt is actually rejecting.

Actually, I'm wondering if the postcondition structure EasyCrypt expects from an "upto bad" call is different—maybe it's `(={res} \/ bad) /\ ...` rather than `(={res} /\ inv) \/ bad`, which would change how the disjunction needs to be framed.

But here's another possibility: with `true` as the invariant, EasyCrypt might not enforce oracle losslessness checks, but with `={Log.qs, LRO.m}`, it generates stricter constraints on the oracle that are failing to verify. event monotonicity). The adversary losslessness depends on oracle losslessness. And oracle losslessness of `Log(LRO).o` depends on `LRO.o` being lossless, which depends on `dptxt_ll`.

So maybe the issue is that EasyCrypt can't automatically verify the losslessness requirements with the non-trivial invariant? But losslessness is independent of the invariant...

Wait, I have another idea. Maybe the issue is not with the `call` itself but with how the postcondition of the `call` matches the overall postcondition. Let me try adding a `wp` step before the `call` to simplify the postcondition.

Actually, in EasyCrypt, there's no explicit `return` in the body (it's handled by `proc`). The last statement is the `a2` call. So the `call` should handle the final postcondition directly.

Hmm, maybe the issue is that the postcondition has some parsing ambiguity with the `\in` operator. Let me try rewriting it with `mem` instead, or adjusting the parenthesization to make the structure clearer.
