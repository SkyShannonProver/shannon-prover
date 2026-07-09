# Tree-0.1 · turn 20 · probe_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:43:06.367Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> z.`

---

Good, the while invariant was committed. Now I need to handle the body preservation subgoal. The goal is a universally quantified phoare:

```
forall z,
phoare[ body : (INV /\ guard /\ variant = z) ==> (INV /\ variant < z) ] = 1%r
```

I need to:
1. Introduce `z` with `move=> z.`
2. Handle the procedure body: `wp; call; wp; skip` or `inline` the call
3. Close with `smt` with appropriate hints

Let me first try `move=> z.` to introduce the variable, then handle the body.
Actually, I might be able to skip the explicit introduction and let `wp; call; auto; smt(...)` work directly on the quantified goal. The tricky part is specifying what the call to `PRPc.PseudoRP.fi` should establish—I need to ensure that after the call, `pi` equals the result of applying `AESi` to the encryption key and ciphertext, which requires understanding the phoare spec for that procedure.

Let me try inlining the procedure definition instead, since that's more straightforward. I'll need to introduce the quantified variable first with `move=> z`, then attempt to inline `PRPc.PseudoRP.fi` to expand its definition directly into the proof.
