# Tree-0.1.1 · turn 1 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:29:52.780Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (equ_cc (p{1}.`1) mr0 ms0).`

---

I'll start by loading the proof intent tool, then read the current state to plan my divergent approach.

The current goal is the first part of the `seq 1 1`: relating `ChaCha(...).enc(k,n,p2)` on the left with `EncRnd.cc(n,p1)` on the right. This is *exactly* the statement of the local lemma `equ_cc`, and the parent's `exists*`/`elim*` of `SplitC2.I1.RO.m{1}` and `SplitC2.I2.RO.m{1}` into `mr0 ms0` was set up precisely to feed that lemma's `mr0 ms0` parameters. The parent's `transitivity{1}` was an over-lowering — the higher-layer move here is a direct `call` of the bridge lemma.
