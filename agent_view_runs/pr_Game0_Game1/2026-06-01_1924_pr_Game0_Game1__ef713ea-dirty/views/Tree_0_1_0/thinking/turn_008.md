# Tree-0.1.0 · turn 8 · commit_tactic

<!-- session 1a85e7aa-e3cb-4466-a034-9c782f2d2105 · 2026-06-02T02:57:57.017Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline*.`

---

The combined tactic was rejected. The issue might be with `rnd` coupling `kp <$ dkeys` (a pair) with `(pk, sk) <$ dkeys` (destructured pair), or with `skip; auto` not being able to close the pure obligation. Let me try a different approach.

Let me read the full view to understand the postcondition, then try a different tactic sequence.

Actually, let me think about the issue. The problem is likely that after `inline*; wp`, the `rnd` needs to couple:
- LHS: `kp <$ dkeys` (samples a pair into `kp`)


- RHS: `(pk, sk) <$ dkeys` (samples a pair, destructuring into `pk` and `sk`)

The `rnd` tactic might not directly handle the different binding patterns. I might need to use `wp` to absorb the `(pk, sk) <- kp` on the LHS first, then `rnd` couples `kp <$ dkeys` with `(pk, sk) <$ dkeys`.

Wait, `wp` should already handle `(pk, sk) <- kp` since it's deterministic. Let me trace through what happens after `inline*`: on the left I have the initial state with empty logs and map, then the key pair sampling, then destructuring that pair. On the right I have the same structure but with direct destructuring in the sampling step.

When I apply `wp`, it absorbs deterministic operations from the end backwards. On the left, the destructuring is deterministic so it gets absorbed, stopping at the sampling step. On the right, the sampling is already the stopping point. This leaves me with the left side sampling `kp` from `dkeys` and the right side sampling `(pk, sk)` directly from `dkeys`, which is exactly what `rnd` needs to couple together.

The real question is whether `rnd` can handle the fact that one side returns a pair while the other destructures it. In EasyCrypt, both are sampling from the same distribution of key pairs, so the destructuring is just syntactic sugar. But after `wp` absorbs the left-side destructuring, the postcondition will have constraints like `pk{1} = kp{1}.1` and `sk{1} = kp{1}.2`, which `rnd` then needs to verify are consistent with the coupling.

The issue might be that `skip` can't discharge the final goal because the postcondition from `rnd` leaves obligations about how `kp` and the destructured `(pk, sk)` relate to each other. Let me try stepping through this more methodically—first applying `inline*` to see the state, then working through `wp` and `rnd` separately rather than as a combined tactic.
