# Tree-0.0 · turn 6 · commit_tactic

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:33:59.327Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{1} BR93(LRO).keygen; inline{1} BR93(LRO).enc.`

---

The view is truncated. Let me read the full view.

Now I can see the full pRHL goal. The two programs are:

Left (BR93_CPA(A).main):
```
Log(LRO).init()                 
(pk, sk) <@ BR93(LRO).keygen()  
(m0, m1) <@ A(Log(LRO)).a1(pk)  
b <$ {0,1}                      
c <@ BR93(LRO).enc(pk, if b then m0 else m1)       
b' <@ A(Log(LRO)).a2(c)         


```

Right (Game1.main):
```
Log(LRO).init()               
(pk, sk) <$ dkeys             
(m0, m1) <@ A(Log(LRO)).a1(pk)
b <$ {0,1}                    
Game1.r <$ drand              
h <$ dptxt                    
c <- (f pk Game1.r, h +^ if b then m0 else m1) 
b' <@ A(Log(LRO)).a2(c)       
```

The right program replaces the actual encryption with a simpler construction that samples random values and XORs them with the chosen message, while maintaining the same interface to the adversary. The precondition ensures both games start with identical adversary state and logging, and the postcondition checks that these conditions are preserved throughout execution. I need to inline the BR93 procedure calls on the left side to match the right side's structure, then use game-hopping techniques to align the identical components step by step, being careful about how the encryption step unfolds since that's where the games diverge. I'm trying different inline tactics to simplify the proof, but I'm realizing that `inline*` might be too aggressive. Let me think about where these games actually diverge and use a more targeted approach with `seq` to split at that point, then handle each section separately. I'm working through how EasyCrypt would actually inline the keygen procedure—when the return value gets assigned to `(pk,sk)`, it combines with the procedure body to produce a fresh variable that gets unpacked into the tuple.

Let me step back and try a different approach: instead of manually inlining everything, I'll use `call` for the adversary interactions and only inline where it matters for the proof.

Now I need to think more carefully about the proof structure itself. The postcondition states that if the adversary's output matches on both sides, then either the random value matches or it appears in the log on the right side. The key insight is that if the random value doesn't appear in the log on the right, then the two games must produce the same output.

The standard EasyCrypt approach here is to split the proof at the encryption step, establish that the prefix is identical across both games, then handle the suffix where the encryption differs. I'll need to show that either the ciphertexts match (when no bad event occurs) or the bad event holds, then call the adversary with the appropriate invariant.

Let me start by inlining the BR93 calls on the left side and see what the game state looks like. I'm trying different tactic combinations to align these programs—maybe I can chain the inline operations together with semicolons, or try a more aggressive approach that inlines multiple procedures at once to expose the underlying structure. I'm realizing that after inlining the encryption procedure, the internal call to the oracle would become visible, so I can then inline that too. Let me start by inlining just the keygen procedure first to see how it goes.
