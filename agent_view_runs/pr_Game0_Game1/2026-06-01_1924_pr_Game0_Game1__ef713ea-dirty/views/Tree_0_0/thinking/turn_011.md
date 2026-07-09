# Tree-0.0 · turn 11 · commit_tactic

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:38:52.564Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline *; wp; rnd; auto.`

---

The `call (_ : true); auto.` was rejected. Let me think about why. The `call` tactic processes from the END. The last statements are:
- Left: `(pk, sk) <- kp` (deterministic assignment)
- Right: `(pk, sk) <$ dkeys` (random sampling)

These aren't calls, so `call` can't process them. I need to handle them first.

Let me try: first use `wp` to handle the deterministic assignment on the left, then `rnd` for the sampling, then `call` for init.


So `wp` will process the deterministic code on the left side, stopping when it hits the random sampling on the right. After applying `wp`, the left program shifts to `Log(LRO).init(); kp <$ dkeys` and the postcondition updates to reference `kp{1}` instead.

Then `rnd` should handle coupling `kp <$ dkeys` on the left with `(pk,sk) <$ dkeys` on the right, since both sample from the same distribution. But I need to be careful with the `call` tactic syntax—it takes a module invariant, not the `==>` implication syntax. And since `Log(LRO).init()` is a concrete procedure call without an adversary argument, I need to find the right invariant to use there.

For concrete procedure calls on both sides, I can try inlining them directly. Using `inline *` would expand `Log(LRO).init()` into its component assignments on both sides, which `auto` should then handle since they're deterministic. The tactic order matters though—`wp` and `rnd` process from the end of the program, so I need to think through what state remains after each step.

After `wp` processes the key generation, the postcondition gets substituted with the concrete values. Then `rnd` couples the random samplings on both sides—`kp` on the left and `(pk,sk)` on the right both come from `dkeys`, so they need to be coupled together. The key insight is that `rnd` in pRHL couples random samplings when both sides sample from the same distribution.

After `wp; rnd`, both sides are left with just `Log(LRO).init()` to process, and I need to figure out whether `inline *` will work at this point or if I should use a different tactic like `call; auto`.

Let me reconsider whether `wp; sim` might be sufficient instead—`wp` handles the deterministic initialization step, and then `sim` should be able to recognize that the remaining sampling operations are semantically equivalent even if the variable names differ structurally.
