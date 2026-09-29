# Tree-0.1 · turn 3 · probe_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:31:47.807Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline *.`

---

Now I need to work through this procedure. The structure is:
1. Deterministic assignments (lines 1-6)
2. A while loop with a call to `PRPc.PseudoRP.fi` (line 7)
3. More assignments and an if-branch with a call to `MAC.verify` (lines 8-9)

For a phoare proof at probability 1 (deterministic), the approach is typically:
- Use `sp` to push through simple assignments
- Handle the while loop with a loop invariant
- Handle calls with `call` tactic
- Use `wp` to work backwards from the postcondition
I need to look up what these procedures do and then construct the appropriate loop invariant and variant for the while loop, since everything here is deterministic. so I need to handle the procedure call inside the loop. Maybe inlining all the calls first with `inline *` would turn everything into deterministic assignments that I can then process with `wp; skip; auto`. Let me explore what `PRPc.PseudoRP.fi` actually does in this context.
