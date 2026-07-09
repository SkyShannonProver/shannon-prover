# Tree-0.1 · turn 6 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:07:23.696Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: true).`

---

It seems like `wp` didn't simplify much — the view still shows the same code structure. Let me read the full view to see what changed.

Good. `wp` processed the RHS's last statement `b <- b' = b0`, which updated the postcondition from `(b'{1} = b{1}) = b{2}` to `(b'{1} = b{1}) = (b'{2} = b0{2})`.

Now the RHS's last statement is `b' <@ A.guess(gy, gz * if b0 then m1 else m0)` and the LHS's last statement is `b' <@ A.guess(c)`.

Now I should use `call (_: true).` to match the A.guess calls on both sides. But wait — there's a subtlety. 

Before the A.guess call on the LHS, there are deterministic assignments like `c <- (g^y, pk0^y * m)` and `m <- if b then m1 else m0` that need to be substituted into the precondition of the call. I'm not sure if `call` in pRHL can work directly with `wp` or if I need to run `wp` first to process these assignments. Let me try `call (_: true).` and see what happens — if those assignments are still in the code, they'll get processed afterward.

Actually, I'm realizing that `call` matches the last call statement on both sides, and both sides now end with A.guess after `wp` removed the deterministic assignment. The question is whether `call (_: true)` automatically processes all the deterministic assignments before the calls like a `wp` would, or if it just matches the calls and leaves the rest for further tactics. I think it's the latter — `call` should match the A.guess calls and leave the deterministic stuff to be handled separately.

In pRHL, `call (_: true)` uses `true` as the relational invariant for the procedure, which means the postcondition requires the arguments to A.guess to be equal on both sides, the results to be equal, and the global state of A to be related. Since A has no module state being modified, after the call succeeds we'd have b'{1} = b'{2} and the glob invariants preserved on both sides.

Now I'm realizing the overall postcondition `(b'{1} = b{1}) = (b'{2} = b0{2})` would need b{1} = b0{2} in addition to b'{1} = b'{2}, which seems problematic. Let me reconsider the approach—maybe I should apply `wp` first to absorb the deterministic assignments before handling the calls. On the left side, there are deterministic assignments for c, m, and pk0, plus a random sampling of b, so `wp` would need to handle that mixture of operations.

Looking at the structure more carefully, the right side also has a random sampling of b0 before the call, so `wp` can't simply skip past both. Let me just try using `call` with a true precondition and see what the system produces. I'm trying to apply the `call` tactic with a true condition to match up the adversary calls on both sides, since the calls are now positioned at the end of both programs as required by pRHL.
