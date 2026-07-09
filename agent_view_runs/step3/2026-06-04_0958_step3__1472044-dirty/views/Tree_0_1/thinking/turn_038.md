# Tree-0.1 · turn 38 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:27:18.916Z -->

**Intent:** `commit_tactic`  
**Payload:** `transitivity{1} { c2 <@ ChaCha(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(ROin, ROout), SplitC1.I2.RO), ROF))).enc(k, n, p2); } (={k,n,p2,glob ChaCha, glob CCRO, glob SplitD, glob SplitC1, glob SplitC2} ==> ={c2}) (true ==> c2{1}=c1{2}).`

---

`call equ_cc` fails to match the procedures regardless of arguments or `conseq`, yet the modules print identically — I cannot diagnose this from the goal text alone, and the L1 profile withholds the error summary by design. Per the prover protocol, when the view is insufficient I should name the missing context rather than reconstruct it from transport internals. Let me record a working note and keep trying distinct strategies.

Let me reconsider: maybe the mismatch is that inlining expanded the `ROin`/`ROout`/`ROF` aliases while `equ_cc` is stored with the alias identities. A robust way to sidestep matching is to apply `equ_cc` as a transitivity bridge whose middle program is written with `equ_cc`'s exact spelling. But first, let me test the cheaper hypothesis that the matcher needs the alias spelling by trying the call with `ROF`/`ROin`/`ROout` names directly available — actually, let me instead try `sim` with the lemma as a hint, which uses a different matcher:
