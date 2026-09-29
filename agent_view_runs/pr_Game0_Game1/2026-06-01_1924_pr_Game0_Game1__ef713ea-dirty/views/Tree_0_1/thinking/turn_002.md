# Tree-0.1 · turn 2 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:30:52.432Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

The `byequiv` tactic was accepted. Now I have 2 remaining goals. The first is the relational judgment:

```
pre = (glob A){1} = (glob A){2} /\ LRO.m{1} = LRO.m{2}

    BR93_CPA(A).main ~ Game1.main 

post = res{1} = res{2} \/ (Game1.r{2} \in Log.qs{2})
```

And presumably a second goal about the probability (the `Pr[G1 : res \/ bad] <= Pr[G1 : res] + Pr[G1 : bad]` part).
 
Looking at the pRHL goal more carefully, I need to prove the equivalence between the two main procedures. My strategy is to inline both sides to see their structure, then establish a coupling that relates their executions.

Since Game1 is essentially BR93_CPA(A) with a modified main procedure, the bodies should be quite similar. I'll step into the procedure and work through the key differences: both sides initialize the log and LRO state, sample the keypair, run the adversary's first phase, flip a bit, and encrypt the chosen message—but they diverge in how they handle the encryption query and what they track in the log. The crucial difference emerges in step 5: BR93_CPA invokes the logged random oracle on a fresh input, which samples from the same distribution as Game1's direct sampling. However, the internal state of the logged oracle diverges after this step depending on whether the random value was previously queried by the adversary.

In step 6, when the adversary makes subsequent queries, it will either retrieve a cached value in BR93_CPA or get a fresh sample in Game1—but this discrepancy only matters if the adversary actually queries that specific value, which would trigger the bad event. The postcondition handles this by asserting that either the results match (because the adversary never queries the critical value) or the bad event occurs (in which case we don't require agreement).

For the pRHL proof, I need to maintain an invariant that keeps the global state synchronized between games while allowing the logged oracle's cache to differ only at the one critical value that Game1 uses.

Now I'm realizing that Game1's random value is only determined after the encryption step, so before that point the oracle's cache is identical on both sides. The invariant needs to evolve as we progress through the proof: initially everything is coupled, then after encryption I couple the random values and the fresh hash output, and the oracle's cache becomes equal except at that one critical point where BR93_CPA has cached the hash but Game1 hasn't queried it yet.

When a2 makes oracle queries in step 6, any query for a value different from the random value will hit the same cache entry on both sides since they only diverge at that single point, so both games produce identical results.

But if a2 queries the random value itself, the two games diverge: the first game returns the cached hash while the second game samples a fresh value since it was never stored, though this discrepancy gets absorbed by the bad event once that random value appears in the query log.

The core constraint I need to maintain is that as long as the random value hasn't been queried yet, the global state and log queries must match between games, and any queries that have been made must return consistent hash values across both sides.

Now I'm thinking through how to structure this as an EasyCrypt proof. The typical approach would be to enter the procedures, handle the initial setup and first adversary call, then manage the divergent encryption step, and finally handle the second adversary call with the appropriate oracle invariant. Since EasyCrypt proofs work backwards, I'd start from the return statement and work through the oracle call during the second phase, then inline the encryption logic, and finally establish the prefix with initialization and the first adversary interaction.

The tricky part is defining the right invariant for the oracle during the second adversary call—I need to account for the fact that the logging oracle wraps the underlying oracle, and the state of the random oracle differs between the two games after encryption, specifically whether the challenge value has been queried.

The standard "upto bad" approach would be to say the states are equal except when the bad event occurs, but that doesn't quite work here since the random oracle maps already diverge. I need a more careful invariant that captures when the oracle behavior is still synchronized despite the state difference.

The key is that before querying `r`, the maps should be identical on all queried points, and `Log.qs` should match across both games. Once `r` gets queried, the results will differ, but I can account for that by allowing the bad event to hold. Let me trace through what actually happens in the encryption oracle when `r` hasn't been queried yet versus after it gets added to the log. When `r` was queried by the adversary in phase one, both games already recorded it in their query logs, so the bad event has already occurred. In the good case where `r` wasn't queried, the memory states between the two games remain coupled through the same sampled value.

Now moving to the second adversary's queries through the logging oracle: when the adversary queries something other than `r`, both games return identical results since the substitution doesn't affect values at different indices, and the memory gets updated the same way in both cases.

But when the adversary queries `r` itself, things diverge—the first game returns the cached value `h` from encryption, while the second game samples a fresh value since it never queried the oracle during encryption. This creates a detectable difference, but it also adds `r` to the query log, triggering the bad event.

The oracle invariant needs to capture this: when `r` hasn't been queried yet, the logs and memory match across both games, but once we condition on `r` not being in the query log, we can establish what the memory values should be.

I'm trying to formalize this as a pRHL invariant for the `call` tactic, which requires an invariant that the oracle itself preserves across both games. I'm realizing the core issue: `LRO.m` actually differs between the two games since BR93_CPA maps `r` while Game1 doesn't, so a simple equality invariant won't work. Instead, I need a more nuanced invariant that allows the maps to differ only on the specific element `r`, using something like an `eq_except` predicate that checks if the maps agree everywhere else. I'm checking whether EasyCrypt's `FMap` theory provides this kind of selective equality operator.

Actually, let me try a different strategy altogether—inlining the oracle code directly and reasoning at the procedural level. After inlining the initialization, key generation, and encryption procedures, both sides become mostly straight-line code with loops for oracle queries. The challenge is that the adversary `A` is abstract and can't be inlined, so the oracle calls through it remain opaque.

Looking at the structure more carefully, the left side runs the initialization and key generation, calls the adversary with the public key, samples a random bit, encrypts using the oracle, then calls the adversary again. The right side follows a similar pattern but uses a game structure where the random value and plaintext are sampled directly, and the ciphertext is constructed from the function evaluation and XOR operation.

The key insight is that when the adversary makes its first call, the oracle's state is identical on both sides since no encryption has happened yet, so I can use a straightforward invariant. But for the second call after encryption, the oracle's internal message differs between the two games, which means I'll need a more sophisticated "upto bad" invariant to handle the divergence.

Let me start working through the proof structure with the procedural tactic and see how the equivalence breaks down.

Actually, I'm realizing the way `byequiv` handles inequalities is more subtle than I initially thought. When proving `Pr[G0 : E] <= Pr[G1 : E'] + Pr[G1 : F]`, it doesn't just give me the relational proof—it also generates side conditions that I need to discharge. The union bound argument requires careful handling of the probability events, and I'm not entirely sure what the second remaining goal is asking for. Let me examine the full workspace to understand what still needs to be proven.

OK, so I have 2 goals:
1. The pRHL judgment (currently shown)
2. Some side condition (second goal)

Let me start proving the pRHL judgment. I'll use `proc` to enter the procedure bodies, then work through the structure.

The key structure:

BR93_CPA(A).main:
```
Log(LRO).init();
(pk,sk) <@ BR93(LRO).keygen();
(m0,m1) <@ A(Log(LRO)).a1(pk);
b <$ {0,1};


c <@ BR93(LRO).enc(pk,b?m0:m1);
b' <@ A(Log(LRO)).a2(c);
return b' = b;
```

Game1.main:
```
Log(LRO).init();
(pk,sk) <$ dkeys;
(m0,m1) <@ A(Log(LRO)).a1(pk);
b <$ {0,1};
Game1.r <$ drand; h <$ dptxt; c <- (f pk Game1.r, h +^ (b ? m0 : m1));
b' <@ A(Log(LRO)).a2(c);
return b' = b;
```

Now I need to connect these two games and show they're equivalent up to the side condition.
