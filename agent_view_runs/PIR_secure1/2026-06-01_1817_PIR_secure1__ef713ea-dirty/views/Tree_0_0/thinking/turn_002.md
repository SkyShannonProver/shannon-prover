# Tree-0.0 · turn 2 · commit_tactic

<!-- session 661f19cc-73dc-4462-9d48-945b0b81b726 · 2026-06-02T01:18:57.434Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline *.`

---

Good, `proc.` was accepted. Now I can see the program structure. Let me read the full view to see the complete goal.

Now I can see the full goal. After `proc.`, I have the program body laid out. The postcondition is `PIR.s{1} = PIR.s{2}`.

My plan:
1. `inline *.` to inline the `query` calls
2. `wp.` to handle the assignments after the loop
3. `while (={PIR.s, j}).` — loop invariant: `s` and `j` are equal on both sides
4. Inside the loop: `wp; rnd.` — identity coupling on `b` works since `s` update depends only on `b` and `j`, not on `i`


5. `skip => /> /#.` or `auto.` to close

Looking at the postcondition `PIR.s{1} = PIR.s{2}`, the two `query` calls after the loop don't modify `PIR.s`, so I can use `inline *; wp` to get past those and the return statement, then set up the while loop invariant. I'll follow the same structure as PIR_secure2's proof.

For PIR_secure1, since `s` doesn't depend on `i` at all—it just gets `j` prepended whenever `b` is true, regardless of the comparison—I can use a simpler identity coupling for the loop invariant.

Continuing with the proof structure...
