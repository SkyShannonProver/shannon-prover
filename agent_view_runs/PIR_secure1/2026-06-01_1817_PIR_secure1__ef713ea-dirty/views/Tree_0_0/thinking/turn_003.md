# Tree-0.0 · turn 3 · commit_tactic

<!-- session 661f19cc-73dc-4462-9d48-945b0b81b726 · 2026-06-02T01:19:17.437Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

`inline *` was rejected — probably because there's nothing to inline at the current program point, or the `query` calls are already inline. Actually, looking at the code, `query` is a procedure call (`r <@ PIR.query(PIR.s)`), but maybe in pRHL mode after `proc`, we need to handle the structure differently.

Actually, the goal is a pRHL goal. The postcondition is `PIR.s{1} = PIR.s{2}`. The `query` calls and `return` don't modify `PIR.s`, so maybe I should use `wp` directly to push past them, or use `sim` to handle the tail.
 
Let me try `wp` to push the weakest precondition past the post-loop code. Though in pRHL, `wp` might struggle with the `call` statements for the `query` procedure. Since `query` only reads `PIR.s` and returns a value without modifying it, and my postcondition only cares about `PIR.s`, I should be able to handle these calls explicitly.

Looking at how `PIR_secure2` was proven with `proc. inline *. wp.`, I'm wondering why that worked there but not here. Let me try just `wp` directly on the post-loop code to see if it can handle the structure, though I need to be careful about how pRHL processes procedure calls.
