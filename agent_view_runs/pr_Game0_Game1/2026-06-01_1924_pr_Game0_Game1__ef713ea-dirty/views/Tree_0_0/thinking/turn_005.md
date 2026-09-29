# Tree-0.0 · turn 5 · commit_tactic

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:33:05.815Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

The `byequiv` was accepted. Now I have 4 goals, and the first one is the relational Hoare logic (pRHL) judgment:

```
pre = (glob A){1} = (glob A){2} /\ LRO.m{1} = LRO.m{2} /\ Log.qs{1} = Log.qs{2}
BR93_CPA(A).main ~ Game1.main


post = res{1} => res{2} \/ (Game1.r{2} \in Log.qs{2})
```

This is the core relational proof showing that the two main procedures are equivalent under this postcondition. I need to examine what both procedures do to understand how to establish this relationship. Let me trace through `BR93_CPA(A).main()` starting with the log initialization...

Now looking at `Game1.main()` to see how it differs from the first procedure...

The critical change is in step 5: instead of deriving `h` through the LRO oracle on the random value, I'm sampling it directly from the plaintext distribution. This breaks the connection between the ciphertext and the oracle's output, which is the key transition for the security reduction.

Now I need to think through when these games actually differ. If `r` hasn't been queried before, the lazy RO will sample a fresh value anyway, so both games look identical. But if `r` was already queried, the LRO returns the cached value while G1 samples fresh—and that's exactly when the adversary can detect the difference. The problem is that the adversary might query `r` later through the oracle, which would expose whether we're using the cached value or a fresh sample. the bad event still triggers in both games when the adversary queries `r`, even though the underlying values differ. So my proof strategy is to use an "up to bad" argument: I'll show the games are equivalent except when the adversary queries `r`, at which point the bad event becomes true. The EasyCrypt approach would involve unfolding the procedure bodies, splitting at the encryption step, and handling the two cases separately.

Now I'm looking at the actual goal structure more carefully. The left side calls procedures like keygen and encryption through the BR93 module, while the right side has inlined some of those procedures but still calls the adversary's functions through the Log wrapper. I need to account for this difference in how the procedures are structured when setting up the proof.
