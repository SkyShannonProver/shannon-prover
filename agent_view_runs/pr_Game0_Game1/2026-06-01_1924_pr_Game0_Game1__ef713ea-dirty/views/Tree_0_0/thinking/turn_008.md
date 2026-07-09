# Tree-0.0 · turn 8 · commit_tactic

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:36:48.447Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 5 4 : (={glob A, glob LRO, glob Log, pk, sk, m0, m1, b}).`

---

Now I can see the full program after all inlining:

Left (14 statements):
```
( 1) Log(LRO).init()                 
( 2) kp <$ dkeys                     
( 3) (pk, sk) <- kp                  
( 4) (m0, m1) <@ A(Log(LRO)).a1(pk)  
( 5) b <$ {0,1}                      


```

Then continuing with the rest: I'm setting up the key pair and message selection, randomly choosing between two messages, then generating a random value to use as a lookup key. If that key hasn't been seen before, I store a fresh random value in the log, retrieve the corresponding entry, and compute the challenge as the encryption of the key paired with the XOR of the hash and selected message. I'm looking at the postcondition and need to understand what it's asserting about the two games. The postcondition states that if b' equals b in the left game, then either b' equals b in the right game, or the random value from Game1 appears in the adversary's query log. Now I need to identify the common structure between these two programs and figure out how to align them efficiently for the proof. I'm working through the proof structure now—I need to split the programs at the call to `A(Log(LRO)).a2(c)` using `seq`, then apply `call` to handle the adversary's behavior while maintaining an invariant that either preserves oracle state equality or captures when the bad event occurs.

Let me try a more direct approach: use `wp` to push the postcondition backward through the deterministic assignments and sampling steps, then handle the adversary call with the appropriate invariant. I'll start by splitting at the key point with `seq` to isolate the prefix from the suffix, which should give me cleaner subgoals for each phase of the proof.
