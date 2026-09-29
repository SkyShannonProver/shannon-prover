# Tree-0.0 · turn 52 · fresh_restart

<!-- session e8f72e76-a384-4fe6-8d81-b6f47e2ab598 · 2026-06-05T17:39:14.434Z -->

**Intent:** `fresh_restart`  
**Payload:** `(none)`

---

This init goal's `forall` requires `bad_L <=> bad_R` but my call-invariant never tracked bad coincidence — it's underivable. Let me check how upto-bad `call` invariants handle the bad flag in the corpus before redoing.

PRG.ec uses a one-directional post (no bad-coincidence needed). My abs-diff form needs it. Let me study a non-target abs-diff `byequiv:bad` + `call` pattern to see how bad-coincidence is structured.

The corpus confirms the fix: abs-diff upto-bad needs the **3-argument** `call (_: B, I, J)` where both the relational invariant `I` and the bad-region invariant `J` carry the bad-coincidence `bad{1} = bad{2}`. My 2-arg call never tracked it, so this `forall` (needing `bad_L<=>bad_R`) is underivable. I must redo the call. Let me confirm the plan with the advisor before spending the turns.

Confirmed — fresh_restart and replay with the 3-arg call. Let me restart.
