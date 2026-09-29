# Tree-0.1 · turn 17 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:49:09.965Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> _; proc; call (LRO_o_ll _); auto=> /=; apply dptxt_ll.`

---

Now the goal is: `forall _, true => islossless Log(LRO).o`

This is asking for the losslessness of `Log(LRO).o`. I can prove it using `Log_o_ll` and `LRO_o_ll`.

Looking at the cross-file lemmas:
- `Log_o_ll (O <: Oracle): islossless O.o => islossless Log(O).o`
- `LRO_o_ll` should exist from the lazy oracle clone

Let me try:
```
by move=> _; apply (Log_o_ll LRO); apply LRO_o_ll.


```

Now I need to verify where `LRO_o_ll` comes from. The ROM clone is instantiated with `clone import ROM as H with ...`, and the Lazy oracle is imported via `import H.Lazy.` This gives me `LRO` and its losslessness lemma. Since `LRO.o` samples from `dptxt` when the key is fresh, the losslessness should follow from `dptxt_ll`.

I'm trying to construct a proof that applies the `Log_o_ll` lemma to `LRO`, which requires showing that `LRO.o` is lossless. Looking at how `BR93_correct` uses `LRO_o_ll _`, I think the right approach is to apply `Log_o_ll` with `LRO` and then provide the losslessness proof.

```
by move=> _; apply (Log_o_ll LRO (LRO_o_ll _)).
```

But I need to verify the exact signature of `Log_o_ll` — it should take an oracle module and a proof that its operation is lossless, then conclude the logged version is also lossless.

Examining the proof pattern from line 148 and the `pr_Game2` case, I see `LRO_o_ll` is indeed parameterized and used with an underscore argument. Let me construct the proof by calling the losslessness lemma on the logged oracle operation, then applying the distribution losslessness properties. I'm trying different proof strategies to handle the losslessness requirement—either using a direct tactic sequence with inlining and SMT solving, or applying a higher-order losslessness lemma for the log oracle wrapper.
