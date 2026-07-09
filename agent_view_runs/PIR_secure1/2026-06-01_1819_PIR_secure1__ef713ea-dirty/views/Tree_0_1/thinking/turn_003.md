# Tree-0.1 · turn 3 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:21:26.304Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline *; wp.`

---

Good, `proc.` committed. Now I can see the procedure body. The programs are marked as "in sync" by EasyCrypt. 

Now I need to handle:
1. The suffix calls to `query` 
2. The while loop
3. The initialization

My plan:
1. `inline *.` to inline the `query` calls
2. `wp.` to absorb the suffix
3. `while (={PIR.s, j}).` to handle the loop
4. Inside the loop: `wp; rnd; skip => /> /#.`
5. `auto.` for initialization

But actually, looking at the `PIR_secure2` pattern more carefully, it uses `inline *. 

Let me reconsider whether inlining is necessary. The postcondition is `={PIR.s}`, and the `query` calls don't modify `PIR.s` or `PIR.s'` — they just return values. So after the calls, the equality should hold from the while loop invariant. But in pRHL, those procedure calls still need to be handled, so inlining them and then using `wp` to absorb the return computation seems like the right approach.

Let me try a more direct tactic and handle the entire remaining proof in one shot.
