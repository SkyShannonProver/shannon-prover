# Tree-0.1 · turn 8 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:24:26.860Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline PIR.query.`

---

The `while` got "invalid last instruction". The route_health says "the while form is plausible, but the current frontier is not positioned at a loop tail." This means the program's last instruction before the postcondition is not the while loop — there are the `query` calls after it. I need to handle the suffix first (the calls to `query`).

After `proc.`, the program structure is:
1. `j <- 0`
2. `(PIR.s, PIR.s') <- ([], [])`


3. `while (j < N) { ... }`
4. `r <@ PIR.query(PIR.s)`
5. `r' <@ PIR.query(PIR.s')`

Since the last instruction is the second `query` call, not the while loop, I need to work backwards from the bottom. I'll handle those query calls first using tactics like `call` to match them up, then tackle the while loop once the suffix is resolved.

Since `query` doesn't modify `PIR.s`, the postcondition `={PIR.s}` should be preserved through both calls. I could use `call (_: ={PIR.s}).` twice to handle them, or try inlining and using weakest precondition reasoning. Let me explore whether inlining helps here.

The manager might be rejecting `inline *` because it predicts no progress, but since both programs have identical `query` calls, maybe they're already synchronized. Rather than risk a blocked tactic, I should try `sp` to absorb the initial assignments first, which will expose the loop as the next instruction to handle.

Actually, the real constraint is that `while` in pRHL requires the loop to be the last instruction on both sides, so I need to eliminate the suffix first. I can use `seq` to split at the while loop and establish an intermediate assertion that the state remains equal, then prove the two query calls preserve that equality—which should be straightforward since they don't modify the relevant state.

Let me map out the instruction sequence to find the right split point.

Hmm, looking at how the PIR_secure2 proof handles this with `inline *` and `wp` to absorb the queries and return, leaving just the while loop. But those tactics are being rejected in my case, so I should try committing `inline *.` directly instead.

Wait, I need to look more carefully at what's happening—the manager said "no progress predicted" on the probe, but that's different from EasyCrypt actually rejecting the tactic. Let me check the logs again... actually, both `inline *` and `wp` show "EasyCrypt rejected this probe or could not use it", so EasyCrypt itself is refusing these tactics. That's strange. Let me think about what the program state looks like after `proc.` to understand why.

Now I see the full goal clearly:

```
pre = true

(1------)  j <- 0                     
(2------)  (PIR.s, PIR.s') <- ([], [])
(3------)  while (j < Top.N) { ... }
(4------)  r <@ PIR.query(PIR.s)      
(5------)  r' <@ PIR.query(PIR.s')    

post = PIR.s{1} = PIR.s{2}
```

The issue is that the last instructions are calls to `PIR.query`, not the while loop. 

I can't apply `while` directly to this structure. Instead, I should split at the while loop boundary using a consequence rule that weakens the postcondition to just `={PIR.s}`, then let the simulator handle the suffix query calls since they don't modify the state anyway.

Now I'm reconsidering the whole approach. The `proc; inline *; wp.` tactic that worked in the `PIR_secure2` proof is getting rejected here, which is strange since there are clearly call sites to inline like the query operations. Let me think about why EasyCrypt might be treating these programs as already synchronized.

Actually, I think the real problem is that `wp` works backward from the end of the program and can only handle assignments, not procedure calls. So it can't process through the query invocations. For `inline`, maybe I need to be explicit about which side to inline on using the side annotations like `inline{1}` or `inline{2}`, or perhaps the undecorated `inline` works for both sides when they're synchronized.

Let me try using the `call` tactic instead, which processes calls from the end in pRHL similar to how `wp` handles assignments. Since both sides have synchronized calls to `query` and the procedure is deterministic without global state modifications, the call invariant should just assert that the state is equal on both sides. I'll attempt `call (_: ={PIR.s}).` to handle the final call, though I need to verify that `call` processes both synchronized calls correctly. I'm reconsidering the approach — maybe I should backtrack and try `proc; inline *; wp.` as a full attempt rather than just probing. The manager said these tactics are accepted but predicted no progress, which suggests they might not actually help with procedure calls like `query`. Let me try a different tactic strategy instead.

I'm thinking about using `conseq` to simplify the postcondition or `seq` to break the program into segments. If I split after the while loop with `seq 3`, I need to figure out whether synchronized programs in pRHL require a single index or explicit side annotations. Let me also reconsider why `inline *` isn't making progress — maybe I need to inline the procedure calls with explicit side markers like `inline{1} PIR.query; inline{2} PIR.query.` to handle them properly.

Actually, I'm realizing that `inline PIR.query` should work on a concrete procedure call, so the "no progress" message is puzzling. Let me try a different angle: use `conseq` to push a stronger postcondition inward, like requiring `={PIR.s, PIR.s'}`, though that still leaves me needing to handle the `i{1} = i{2}` constraint that `sim` left behind. Maybe I can weaken the goal first with `conseq` to avoid requiring `i` in the postcondition.

Looking at how `PIR_secure2` succeeds with `proc. inline *. wp. while (={PIR.s', j}).`, I'm wondering if `inline *` and `wp` actually do work for my case but the manager is incorrectly predicting no progress. Let me try committing `inline *.` directly and see what happens.

But wait—the manager said it would auto-revert any commit if it detects no progress, so I can't bypass that prediction. Instead, I'll try being more specific with `inline PIR.query.` to target just that procedure rather than inlining everything.
