# Tree-0.1 · turn 10 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:43:32.157Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: (={Log.qs}) /\ (forall x, x <> Game1.r{2} => LRO.m{1}.[x] = LRO.m{2}.[x]), (Game1.r \in Log.qs){2}).`

---

Good, I'm back to the state after `proc` + `inline`. Now let me try the "upto bad" call with a better invariant. I know the comma syntax works from the test with `true`.

Let me try `eq_except` directly:

```
call (_: eq_except (pred1 Game1.r{2}) LRO.m{1} LRO.m{2} /\ ={Log.qs}, Game1.r{2} \in Log.qs{2}).
```

Wait, this was already rejected. Let me try without `pred1`:


Trying different formulations of the invariant...

I could express it as a conjunction stating that the log queues are equal everywhere, and the map entries match except at the specific record value. Or maybe the issue is that `eq_except` isn't accessible in this context, so I should expand it manually into a more explicit form.

Looking back at what worked versus what failed, the key difference seems to be where I place the side annotations—putting them on the outside of the entire expression rather than on individual variables. Let me adjust the placement...

Actually, I'm wondering if I can simplify this further by dropping the `eq_except` and `pred1` constructs entirely and just working with the core equality and membership constraints.

The key insight is that the maps should agree on all keys that have been queried so far, and when a new query comes in, I need to ensure the invariant holds. Let me try expressing this as: the logs are identical, the maps agree on all previously logged keys, and the queried element is in the log.

But I'm running into a problem — if a fresh query `x` arrives that wasn't previously queried and `x ≠ r`, then the maps might disagree at `x` since the invariant only constrains values at keys already in the log. This weaker invariant breaks down because I can't guarantee both sides compute the same thing for a new key that wasn't set during encryption. if `x \notin Log.qs` and `x \neq r`, then `x \notin dom(LRO.m{1})` and `x \notin dom(LRO.m{2})` (since the only difference is at `r`)

Wait, that's not quite right either. `LRO.m` is modified by:
1. `Log(LRO).o` calls during `a1` — these modify `LRO.m` on both sides identically
2. The encryption step on LHS — modifies `LRO.m{1}` at `r`

So after encryption:
- `LRO.m{1}.[x] = LRO.m{2}.[x]` for all `x \neq r`
- `LRO.m{1}.[r]` is set (from encryption), `LRO.m{2}.[r]` might not be

So `eq_except (pred1 r) LRO.m{1} LRO.m{2}` is exactly right — the maps agree everywhere except possibly at `r`. During `a2`'s oracle calls, queries at `x \neq r` preserve this invariant since both sides update identically, while querying `x = r` triggers the bad event. The `eq_except` invariant seems like the right approach, but EasyCrypt rejected it, so I need to figure out what's going wrong with how it's being formulated. I'm reconsidering the order of conjuncts in the precondition—maybe putting `={Log.qs}` first before the `eq_except` clause makes a difference. Looking back at my earlier attempts, I notice the escaping of backslashes in the JSON payload might affect how the tactic parses, though both versions should be equivalent. Let me try being more explicit with parentheses and grouping...

Actually, I'm wondering if `eq_except` might not be in scope after the ROM clone, so I should fall back to writing out the condition explicitly with a forall quantifier instead.
