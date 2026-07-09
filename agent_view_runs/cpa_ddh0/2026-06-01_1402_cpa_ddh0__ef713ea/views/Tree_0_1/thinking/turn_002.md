# Tree-0.1 · turn 2 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:04:26.483Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

The `byequiv` was accepted. Now I have a pRHL goal:

```
pre = (glob A){2} = (glob A){m} /\ (glob A){1} = (glob A){m}
CPA(ElGamal, A).main ~ DDH0(DDHAdv(A)).main
post = res{1} = res{2}
```

Now I need to unfold the procedures. Let me use `proc.` to unfold the main procedures, then `inline *` to inline all the internal calls (ElGamal.kg, ElGamal.enc, DDHAdv.guess).


I'll start with `proc.` to unfold everything, then apply `inline *` to handle the internal procedure calls in one go.
