# Tree-0.0 · turn 4 · probe_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:31:55.819Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline PRPc.PseudoRP.fi.`

---

The goal text was truncated. Let me read the full view to see what `inline *` produced.

So `inline *` was rejected. This is a phoare goal, and `inline *` probably doesn't work in this context. Let me think about the right approach.

The procedure has two call sites:
1. `pi <@ PRPc.PseudoRP.fi(ek, ci)` inside the while loop
2. `b <@ MAC.verify(mk, p', t)` inside the if block

Since this is a phoare goal (one-sided), I need to handle the calls differently. Let me think about the approach:

For a phoare correctness proof of a deterministic procedure, the standard approach is:
1. Use `sp` to process initial assignments
2. Use a `while` loop with a loop invariant that tracks the relationship between `padded` and `cbc_dec`
3. Handle the calls inside the loop by inlining or using `call` with a simple spec
4. After the loop, use `wp` and `sp` to process the remaining code
5. Close with `skip` and `smt`

But `inline *` was rejected, so maybe I need to be more specific about which procedures to inline. Let me try a different approach instead.

For this phoare proof, I should work through it systematically: use `sp` to consume the initial assignments before the loop, then handle the while loop with an appropriate invariant, and for the call inside the loop I can either inline it or use `call` with a spec. Let me start by trying to inline the specific procedure directly.
