# Tree-0.1 · turn 21 · commit_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:43:18.147Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> z.`

---

Good, `move=> z.` was accepted and now I can see the clear phoare body goal. The body is:

```
(1) ci <- nth witness c i
(2) pi <@ PRPc.PseudoRP.fi(ek, ci)
(3) padded <- padded ++ [s - pi]
(4) s <- ci
(5) i <- i + 1
```

I need to handle the call `pi <@ PRPc.PseudoRP.fi(ek, ci)`. I need to know that `pi = AESi ek ci` after the call. 

Let me try inlining the procedure definition to simplify the proof.
