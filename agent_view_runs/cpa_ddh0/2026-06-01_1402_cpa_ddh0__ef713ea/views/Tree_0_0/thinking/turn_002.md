# Tree-0.0 · turn 2 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:03:20.338Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

Good, `byequiv => //.` was accepted. Now I'm in pRHL mode with:

```
pre = (glob A){2} = (glob A){m} /\ (glob A){1} = (glob A){m}
CPA(ElGamal, A).main ~ DDH0(DDHAdv(A)).main
post = res{1} = res{2}
```

Now I need to unfold both `main` procedures. The next step is `proc.` to unfold the top-level procedures, then inline the concrete module calls.

Actually, let me think about the structure more carefully.


Looking at the two main procedures, the CPA game runs the key generation, has the adversary choose two messages, samples a random bit, encrypts one of them based on that bit, and returns whether the adversary guesses correctly. The DDH0 procedure is starting to set up its own variables but appears to be cut off.

Continuing with the DDH setup, I'm sampling random exponents, computing the group element as g to the power of their product, then calling the DDH adversary's guess function with the three group elements. The guess function mirrors the CPA structure—it has the adversary choose messages using the first group element, samples a random bit, and checks if the adversary can guess correctly when given the second element and a combination of the third element with one of the chosen messages.

So the strategy here is to inline these procedures to show how the CPA game reduces to the DDH assumption. I should start with the proc tactic to unfold the definitions.
