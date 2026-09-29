# Tree-0.0 · turn 8 · probe_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:25:48.864Z -->

**Intent:** `probe_tactic`  
**Payload:** `seq 2: (={PIR.s, j}).`

---

`inline PIR.query.` was also rejected. The programs are "in sync" so maybe inline doesn't work in this mode.

Let me try a completely different approach. Let me undo `proc.` and try using `while` directly, or try `seq` to cut the code, or use `conseq` to reformulate.

Wait, I want to check: the full goal after `proc.` — the truncated part. Let me read the full workspace view to see the complete goal.

Now I see the full goal. The programs are "in sync" with 5 statements:
1. j <- 0
2. (PIR.s, PIR.s') <- ([], [])
3. while loop
4. r <@ PIR.query(PIR.s)
5. r' <@ PIR.query(PIR.s')

post = PIR.s{1} = PIR.s{2}

And "programs are in sync" means both sides have the same code, so EasyCrypt prints them in one column.

The issue is that `inline *`, `inline PIR.query`, `wp`, and `sp` all fail. 

Since the programs are syntactically identical but EasyCrypt is treating them differently, I should try working with the while loop directly using a relational Hoare logic tactic, then cut after it to establish the invariant. Alternatively, I could approach the final calls from the back using a consequence rule to set up the right postcondition. I need to use `seq` to consume the initialization statements before applying the while tactic, cutting after the first two statements with a postcondition that tracks the relevant variables across both sides of the proof. I'm realizing that after both sides execute the initialization steps, the equality condition `={PIR.s, j}` should hold since j becomes 0 on both sides and PIR.s becomes [] on both sides, regardless of the initial state. So I can use this as the intermediate assertion to cut the proof.
