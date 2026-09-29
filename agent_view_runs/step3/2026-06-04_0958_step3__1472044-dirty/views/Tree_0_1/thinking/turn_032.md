# Tree-0.1 · turn 32 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:20:57.461Z -->

**Intent:** `commit_tactic`  
**Payload:** `exists* (SplitC2.I1.RO.m{1}), (SplitC2.I2.RO.m{1}); elim* => mr0 ms0; call (equ_cc (p{1}.`1) mr0 ms0).`

---

That's not the issue. The real problem is the EC idiom: `equ_cc`'s parameters `mr0`/`ms0` depend on the **initial memory** (`ROin.m{1}`, `ROout.m{1}`), and `call` can't take memory-indexed expressions as lemma arguments directly — they must first be generalized into logical variables with `exists*`/`elim*`. Let me do that.
