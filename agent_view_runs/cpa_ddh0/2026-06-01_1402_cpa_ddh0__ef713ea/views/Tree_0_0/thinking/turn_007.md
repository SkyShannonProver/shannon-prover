# Tree-0.0 · turn 7 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:08:33.957Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: true).`

---

The `call (_: ={glob A}).` was rejected. Let me check the error. The issue might be that the last statements on both sides aren't aligned as calls to the same procedure. On the left, the last statement is `b' <@ A.guess(c)` and on the right it's `b' <@ A.guess(gy, gz * if b0 then m1 else m0)`. But before the A.guess call, there are deterministic assignments on both sides that need to be handled first.

Actually, looking at the programs more carefully:

Left:


...
5. b <$ {0,1}
6. pk0 <- pk
7. m <- if b then m1 else m0
8. c <- (g ^ y, pk0 ^ y * m)
9. b' <@ A.guess(c)

Right:
...
7. b0 <$ {0,1}
8. b' <@ A.guess(gy, gz * if b0 then m1 else m0)

The problem is that `call` matches the last statement on both sides, but the left side has deterministic computations (lines 6, 7, 8) between the random sampling and the procedure call that need to be processed first before attempting to match the calls.

Maybe I should apply `wp` again before `call`, or perhaps the tactic stopped at the A.guess calls without processing the preceding statements. Let me check the actual error message to see what's happening.

The manager result doesn't include the actual EasyCrypt error message. Let me check if there's a followup file with more details.

The error message isn't very detailed. The issue with `call (_: ={glob A}).` might be that:

1. The last procedure call on the left side has deterministic assignments between it and the current proof point. The `call` tactic in pRHL needs the LAST statement (before the postcondition) to be a procedure call on BOTH sides.

Looking at the current state again:

Left (after wp from end):
```
sk0 <$ dt                   
y <$ dt                     
(pk, sk) <- (g ^ sk0, sk0)  
(m0, m1) <@ A.choose(pk)    


b <$ {0,1}                  
pk0 <- pk                   
m <- if b then m1 else m0   
c <- (g ^ y, pk0 ^ y * m)   
b' <@ A.guess(c)            
```

Right (after wp from end):
```
x <$ dt                        
y <$ dt                        
gx <- g ^ x                    
gy <- g ^ y                    
gz <- g ^ (x * y)              
(m0, m1) <@ A.choose(gx)       
b0 <$ {0,1}                    
b' <@ A.guess(gy, gz * if b0 then m1 else m0)
```

The issue is that on the left side, there are deterministic assignments (`pk0 <- pk`, `m <- if b then m1 else m0`, `c <- (g ^ y, pk0 ^ y * m)`) happening after the `A.choose` call but before the final `A.guess` call, whereas the right side goes directly from `A.choose` to `A.guess`. The `call` tactic expects both sides to end with a procedure call without intervening deterministic code. I think the real issue is that the postcondition after `wp` is `(b'{1} = b{1}) = (b'{2} = b0{2})`, but the `call` tactic expects the postcondition to isolate just the variables modified by A.guess—in this case `b'`. Since the postcondition still references `b{1}` and `b0{2}` which aren't touched by the procedure, those need to be preserved as part of the invariant that `call` carries through. Inv ∧ (arguments equal)
- Post: Inv ∧ (results equal)

The underscore `_` means we don't provide a specific proof of this fact. But EasyCrypt needs to discharge it.

The postcondition is `(b'{1} = b{1}) = (b'{2} = b0{2})`. After `call (_: ={glob A})`, EasyCrypt would need:
- `b'{1} = b'{2}` (from the call) and `={glob A}` (preserved)
- Then the remaining post: `(b'{1} = b{1}) = (b'{2} = b0{2})`

But this post involves `b{1}` and `b0{2}` which are NOT modified by A.guess. So after the call, we'd need `={glob A} ∧ b'{1} = b'{2}` to imply the postcondition—but that's only possible if we know `b{1} = b0{2}` beforehand. The real problem is that the postcondition can't be established from just the equality of results without already knowing the relationship between `b{1}` and `b0{2}`. I tried using `wp` to handle this, but it only processed the rightmost deterministic assignment, leaving me with the same postcondition where `b{1}` and `b0{2}` still need to be propagated through the proof.

I think the solution is to restructure the proof by handling the deterministic assignments and boolean sampling before the call, then applying `call` with a simpler invariant that doesn't require local variable relationships. The issue is that `call` for A.guess needs the right postcondition, but after `wp` processes the deterministic assignment, the postcondition becomes something like `(b'{1} = b{1}) = (b'{2} = b0{2})`, which doesn't match what `call` would produce. I need to reconsider the order of operations and how the postconditions compose through each step. I'm working through the weakest precondition calculation more carefully—if `b'{1} = b'{2}` holds after the call, then the equality `(b'{1} = b{1}) = (b'{2} = b0{2})` reduces to checking whether `b{1} = b0{2}`, which becomes a necessary precondition. The issue is that the `call` tactic with the `={glob A}` syntax might not automatically perform this WP computation, so I may need to use `conseq` or another approach to make it work.

Let me try a completely different strategy—instead of the current tactic sequence, I'll work backwards from the end more aggressively, or perhaps use `call` with explicit losslessness arguments. The real problem might be simpler: EasyCrypt may require the function arguments to be in a specific compatible form, and the `call` tactic can't unify `A.guess(c)` on the left side with whatever form it expects.

Actually, thinking about it more carefully—since `ctxt = group * group`, these should be equivalent calls syntactically, but EasyCrypt might be treating them differently. Let me try using `wp` more aggressively to handle all the deterministic assignments first, leaving just the adversary calls and sampling operations to deal with separately. I'm wondering if I should use `wp` with a step count to process instructions incrementally rather than all at once. The real problem seems to be that after processing the assignment, the `call` tactic fails because the left side has `A.guess(c)` where `c` is a context pair, while the right side calls `A.guess` with two separate arguments—they're semantically equivalent but EasyCrypt needs the argument forms to match exactly. Let me try a different approach. What if I use `wp` again to try to process more assignments? Or use `conseq` to massage the postcondition?

Actually, I think the real issue might be simpler: maybe `call` in EasyCrypt doesn't work with the `_` placeholder when used in this context. Let me try `call (_: true).` instead.

Or maybe the issue is that A.guess is declared as taking a `ctxt` argument (a pair), and on the right side, the inlined call passes two arguments. EasyCrypt might not be able to match these. In that case, I might need to handle the assignment `c <- ...` on the left with `wp` first.

The problem is that `wp` works from the bottom up, and the last statement on the left is the call `b' <@ A.guess(c)`, so `wp` can't push past it to handle the deterministic assignment above it. I need to find a way to deal with the sequence of the assignment followed by the call together. I'm considering a different approach to the whole proof—let me backtrack and try a simpler tactic sequence that processes the program more directly. The issue seems to be with how `call` interacts with the proof state, so I should either undo the recent steps and retry without the swap, or use a checkpoint to reset and try a cleaner sequence from after inlining everything.
