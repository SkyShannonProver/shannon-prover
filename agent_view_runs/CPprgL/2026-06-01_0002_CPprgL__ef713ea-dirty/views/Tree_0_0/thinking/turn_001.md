# Tree-0.0 · turn 1 · probe_tactic

<!-- session f55c19a1-708a-48da-89bc-a5f57fc9c2a7 · 2026-06-01T07:03:32.468Z -->

**Intent:** `probe_tactic`  
**Payload:** `by move=> PprgL; proc; sp; if=> //; call PprgL; wp.`

---

Let me analyze the current proof goal and workspace view carefully.

The lemma to prove is `CPprgL`:
```
lemma CPprgL (A <: Adv) (F <: ARF) (P <: APRG):
  islossless P.prg =>
  islossless C(A,F,P).CP.prg.
```

Looking at the current goal:
```
A(F0 : ARF, P0 : APRG) : Adv
F : ARF
P : APRG
------------------------------------------------------------------------
islossless P.prg => islossless C(A, F, P).CP.prg


```

The `CP.prg` procedure initializes a witness value, then conditionally calls `P.prg()` if a counter is below a threshold before returning. Since the suggested tactic is `proc; auto => />.`, this should be a straightforward losslessness proof that reduces to showing `P.prg` is lossless.

```
The goal is an implication at the ambient level, so I need to introduce the hypothesis first with `move=> H`, then apply `proc` to unfold the procedure and work through the losslessness proof. The seed tactic `proc; auto => />.` might work after introducing the hypothesis, or I could try a more explicit approach like `move=> H; proc; sp; if => //; call H; wp` to handle the conditional and procedure call systematically.
```
lemma CFfL (A <: Adv) (F <: ARF) (P <: APRG):
  islossless F.f =>
  islossless C(A,F,P).CF.f.
proof. by move=> FfL; proc; sp; if=> //; call FfL; wp. qed.
```

This similar lemma shows the pattern I should follow, so let me test this approach.
