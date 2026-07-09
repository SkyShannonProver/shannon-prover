# Tree-0.1 · turn 2 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:00:32.447Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline Split1.IdealAll.MainD(G8(BNR_Adv(A)), SplitC2.RO_Pair(ROin, ROout)).distinguish G8(BNR_Adv(A), SplitC1.RO_Pair(SplitC2.RO_Pair(ROin, ROout), SplitC1.I2.RO)).distinguish.`

---

Now I have an equiv between the two games with `={glob A}` precondition and `res{1}=res{2}` postcondition. The difference is the encryption oracle (real ChaCha via split-RO on the left, random `EncRnd` on the right), bridged by the `equ_cc` helper. 

I need to unfold the game wrappers down to the adversary call. Let me inline the concrete wrapper procedures on both sides.
