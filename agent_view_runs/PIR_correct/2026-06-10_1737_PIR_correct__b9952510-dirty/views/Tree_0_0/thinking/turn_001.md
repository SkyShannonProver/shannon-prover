# Tree-0.0 · turn 1 · commit_tactic

<!-- session 50746433-7704-4ffd-84cc-4a2de77aaa16 · 2026-06-11T00:39:02.874Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> hi0.`

---

I'll start by reading the current workspace view to understand the proof state.

Let me read the followup and the source file to understand the lemma context.

Let me locate the PIR.ec source file.

I now understand the lemma. `PIR_correct` states `Pr[PIR.main(i0) : res = a i0] = 1%r` — the result is *deterministically* correct (probability 1), independent of the random bits. My plan: `byphoare` with a loop invariant `big a s +^ big a s' = (if i0 < j then a i0 else zerow)`, since for `j≠i0` the index either cancels (added to both) or is absent, and for `j=i0` it lands in exactly one of `s`/`s'`.

Let me start the proof by introducing the hypothesis.

I'll commit the first tactic to introduce the hypothesis.
