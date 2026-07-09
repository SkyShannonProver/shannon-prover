# Tree-0.0 · turn 10 · inspect_context

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:34:40.836Z -->

**Intent:** `inspect_context`  
**Payload:** `tactic_forms`

---

The tactic forms for call are in equiv/pRHL context. But I'm in phoare context. For phoare goals, `call` might have different forms. Let me think about the phoare-specific approach.

In phoare logic, for a procedure call `x <@ M.f(args)`, I can use:
- `ecall (PHOARE_SPEC)` — use a phoare specification for the call
- Or construct the spec inline

Actually, let me re-think the overall approach. The `mee_decrypt_correct` phoare spec says:
```
phoare [MEEt.MEE(PRPc.PseudoRP, MAC).dec : pre ==> post] = 1%r
```

The procedure body is deterministic since the calls to `PseudoRP.fi` and `MAC.verify` don't involve sampling, so the probability is trivially 1. The real challenge is handling the procedure calls nested inside the loop and conditional blocks—I can't just call `ecall` directly on them.

Let me structure the proof systematically: first use `sp` to consume the initial assignments and bind the variables, then apply `while` with an appropriate loop invariant connecting `padded` to the CBC decryption result, handle the `PseudoRP.fi` call inside the loop, and finally deal with the `if` statement and `MAC.verify` call after the loop terminates. I need to figure out the exact syntax for the `while` tactic in this phoare context—it likely requires specifying an invariant, variant, and probability bound per iteration.

```
conseq (_: pre ==> post) (_: true) => //.
```

This approach splits the phoare goal into two manageable pieces: a standard Hoare triple for correctness and a separate losslessness obligation, which I can then discharge with `proc; inline *` and other standard tactics.

But I'm realizing the `hoare` tactic in a phoare context actually decomposes `phoare [f : P ==> Q] = p` differently than I expected—it produces a Hoare triple plus a probability constraint, and when something goes wrong with that decomposition, I end up with nonsensical goals like `0%r = 1%r`. Let me think through what the actual decomposition should be. Maybe the `hoare` tactic doesn't handle exact equality bounds like `[=]` properly, only inequality bounds. Let me try using `conseq` instead to explicitly set up the consequence rule with the probability condition.

Actually, I should step back and try a different tactic flow: use `sp` to process the assignments before the loop, which transforms the goal into a phoare statement about the remaining code. Then for the while loop, I need to establish a loop invariant, a variant for termination, and verify that each iteration maintains the probability bound of `1%r` since the loop body is deterministic.
