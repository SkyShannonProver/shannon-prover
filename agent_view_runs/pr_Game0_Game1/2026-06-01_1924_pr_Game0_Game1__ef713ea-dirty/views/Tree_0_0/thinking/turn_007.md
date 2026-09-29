# Tree-0.0 · turn 7 · commit_tactic

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:36:10.844Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{1} LRO.o.`

---

Good, the inlining was accepted. The view is truncated, let me read the full view.

Now I can see the full program structure after inlining:

Left:
```
Log(LRO).init()                 
kp <$ dkeys                     
(pk, sk) <- kp                  
(m0, m1) <@ A(Log(LRO)).a1(pk)  
b <$ {0,1}                      
pk0 <- pk                       
m <- if b then m0 else m1       
r <$ drand                      
h <@ LRO.o(r)                   
c <- (f pk0 r, h +^ m)          


```

Right:
```
Log(LRO).init()               
(pk, sk) <$ dkeys             
(m0, m1) <@ A(Log(LRO)).a1(pk)
b <$ {0,1}                    
Game1.r <$ drand              
h <$ dptxt                    
c <- (f pk Game1.r, h +^ if b then m0 else m1) 
```

The key differences are that the right side inlines the message selection directly into the ciphertext computation, stores the random value as a game variable, and replaces the oracle call with a direct plaintext sample. Now I need to check what happens when the adversary makes its second query. } \in Log.qs{2})`

The programs are very similar now. Let me trace through:

1. Init: identical call `Log(LRO).init()` — both sides
2. Keygen: Left does `kp <$ dkeys; (pk,sk) <- kp`, Right does `(pk,sk) <$ dkeys` — equivalent
3. Adversary a1: identical `(m0,m1) <@ A(Log(LRO)).a1(pk)` — both sides
4. Bit: `b <$ {0,1}` — both sides
5. Encryption:
   - Left: `pk0 <- pk; m <- if b then m0 else m1; r <$ drand; h <@ LRO.o(r); c <- (f pk0 r, h +^ m)`
   - Right: `Game1.r <$ drand; h <$ dptxt; c <- (f pk Game1.r, h +^ if b then m0 else m1)`
6. Adversary a2: `b' <@ A(Log(LRO)).a2(c)` — both sides

The key difference is in step 5: left queries `LRO.o(r)` while right samples `h <$ dptxt`.

For the proof strategy, I'll use `seq` to handle the common prefix through the bit sampling, then reason about how the LRO query and plaintext sampling differ, and finally handle the common suffix with the second adversary call. The challenge is showing these divergent encryption steps are equivalent in the security context. r <$ drand
h <@ LRO.o(r)
c <- (f pk0 r, h +^ m)
b' <@ A(Log(LRO)).a2(c)

On the right side, I have Game1.r <$ drand, h <$ dptxt, then c gets constructed with the conditional for m baked in, and finally the a2 call.

Let me count the left statements more carefully to find where to split. After the initial setup with keygen, key assignment, and the a1 call, I have the random bit b, then pk0 assignment, the conditional message assignment, the random sampling for r, the LRO query for h, the ciphertext construction, and the a2 call. I need to identify which statements are identical between the two games so I can use seq to split at the right point.

The prefix that should match is init, keygen, a1, and the random bit b. Then everything after that differs in how the message and randomness are handled. I'm thinking seq at position 5 on the left and position 4 on the right, with the invariant tracking the adversary state, the LRO state, the Log state, the bit b, both messages m0 and m1, and the keys. I'm realizing this approach is getting unwieldy, so let me try something more direct. Instead of breaking down the proof sequentially, I should use the `call` tactic to handle the final adversary invocation where both programs make the same call, then work backwards through the remaining differences. The key insight is that if I can establish the precondition for that call—that the challenge values are equal and the global state matches—then the postcondition should follow naturally, accounting for the bad event in the process. } => b'{2} = b{2} \/ (Game1.r{2} \in Log.qs{2})`, the postcondition hinges on whether the adversary queried `Game1.r`. If it didn't, then the ciphertexts stay equal and the bit values match across games. If it did query `Game1.r`, the bad event becomes true and the postcondition holds trivially. So I need an invariant for the call that tracks the shared state, the oracle messages, and whether the adversary can trigger the bad event.

But there's a complication: the LRO maps diverge between G0 and G1. After encryption, G0 has `r -> h` stored in its oracle map while G1 doesn't, since G1 sampled `h` directly. This means when the adversary queries the oracle later, it's operating on different internal states depending on which game it's in.

The key insight is that the games only diverge when the adversary queries `r` to the oracle—in G0 it retrieves the cached `h` value from the map, but in G1 it gets a fresh random sample. This is precisely when the bad event `r ∈ Log.qs` triggers. So I need to formalize an invariant that captures this LRO state difference while tracking when the adversary's queries cause the games to split.

Actually, I'm overcomplicating this. A cleaner approach is to use a disjunctive invariant: either the games remain perfectly synchronized across all state (including the LRO map and logs), or the bad event has occurred. This collapses the complex case analysis into a much simpler statement.

But wait, that's too restrictive for the LRO itself — even without the bad event, the left and right games diverge on what's stored in the LRO map at the key `r`. So I need to be more careful about what I'm actually tracking.

Let me try inlining the LRO oracle operation on the left side to see if that helps me reason about the state more precisely.

Inlining the oracle call... I'm realizing the key issue: when `r` is freshly sampled in both games, it could theoretically already exist in the random oracle's memory from the adversary's earlier queries, which would cause the two games to diverge in their responses. Since `r` comes from a continuous distribution and the adversary has only made finitely many queries, the probability of collision is negligible, but I need to be careful about when exactly this matters for the proof. O).o`. So `r` is NOT added to `Log.qs` by the encryption step.

But `r` is added to `LRO.m` (the lazy RO map). And if the adversary later queries `r` through `Log(LRO).o`, then:
- `r` is added to `Log.qs`
- `LRO.o(r)` returns the stored value in G0, or samples fresh in G1

So the bad event `Game1.r \in Log.qs` captures whether the adversary (in a1 or a2) queried the challenge randomness.

Now for the case split: if `r` doesn't appear in `Log.qs` after a1 and also isn't in `LRO.m`, then the encryption step in G0 and G1 behave identically since both sample a fresh random value for `r`.

Wait, I need to check whether `Log` actually tracks all `LRO` queries. Looking at the code, `Log(LRO).o` logs queries and calls `LRO.o`, but `BR93(LRO).enc` calls `LRO.o` directly through its `H` parameter rather than going through `Log(LRO).o`. So `Log.qs` only captures queries made by the adversary through the logged interface, not internal calls from the encryption procedure.

Since `BR93` is instantiated with `LRO` directly in the game, the encryption query hits `LRO.o` but bypasses the `Log` wrapper entirely. This means `Log.qs` contains only the adversary's queries while `LRO.m` contains everything including the encryption query, so after encryption the logged query sets are identical between both games but the underlying `LRO` state differs. So after initialization, `Log.qs` and the domain of `LRO.m` should be equivalent—both track the same set of queries made through the Log wrapper, since every query to `Log(LRO).o(x)` simultaneously adds `x` to both `Log.qs` and `LRO.m`. not quite right. `Log.qs` is a list that can have duplicates, but every queried point ends up in `dom(LRO.m)`. So `dom(LRO.m)` equals the set of all queried points, which is the set of elements in `Log.qs` (assuming no other LRO queries happen), since the only oracle access goes through `Log(LRO).o`, which logs and then queries `LRO.o`.

After a1, when the fresh `r` is sampled, if `r` happens to be in `Log.qs` — meaning the adversary queried it during a1 — then the games diverge: in G0, `LRO.o(r)` returns the stored value, but in G1, a fresh random value is sampled instead.

In the good case where `r` is not in `Log.qs`, both games sample a fresh value from the same distribution, so `h` has identical distribution and the ciphertexts compute the same way. The logs and LRO maps remain consistent across the games until the bad event occurs.

Now during the adversary's second phase queries: if they ask for any key besides `r`, both LROs return matching values since they either agree on that key or both sample fresh identically. But if they query `r` directly, G0 returns the stored encryption hash while G1 samples a fresh value, which is where the games can diverge.

The key insight is that this divergence only matters when `r` ends up in the query log, which is exactly the bad event we're tracking. So the proof strategy needs a careful coupling that preserves equivalence unless the bad event occurs, plus synchronized oracle behavior during the adversary's second phase.

This is a standard lazy random oracle with one distinguished entry pattern, but it demands precise invariant management. I should look for an efficient EasyCrypt tactic sequence—maybe something involving eager sampling or a similar pattern that's already established in the library.

Let me try splitting the proof at the encryption step using a sequence tactic to first establish that the initialization and first adversary phase are identical across both games, then handle the critical suffix where the sampling strategies diverge.

Writing EasyCrypt proof... I'm looking at the left program and need to inline the `LRO.o` call to expose the conditional logic inside the lazy random oracle lookup. Once I expand that, I can use control flow tactics to align the random sampling on both sides and work through the proof sequentially.

I'm considering a few different strategies here—either manually sequencing through the prefix, handling the conditional with `if` and `rnd`, then calling the adversary suffix, or trying something more aggressive like `sim` to automatically handle identical parts. But `sim` won't work since the programs are structurally different with different encryption steps, so I need to find a more targeted approach rather than trying to align everything manually.

Let me inline the oracle definition on the left side to expose the conditional structure, then I'll have a clearer picture of what needs to be proven.
