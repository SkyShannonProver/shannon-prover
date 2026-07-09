# Tree-0.0 · turn 21 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:46:14.128Z -->

**Intent:** `commit_tactic`  
**Payload:** `case: hp => [[hu hsz hw hg] _].`

---

The compound destructure was the issue; single-name works. Now the `u'` mu bound. The key: `g_^x = (g^w)^x = g^(w·x)`, so the preimage involves dividing by `w`. Let me look up the exact field-division lemma (`w*x/w = x` with `w≠0`) before building it.

Cleaner: use `logb`/`logbK` (log base `g_`) so the division is hidden inside `logbK`, avoiding manual field algebra. I need `unit (loge g_)` (= `unit w`) from `w ≠ zero`, and the `mu1 (dt\pred1 u) ≤ 1/(order-1)` bound. Let me find the nonzero→unit lemma.

Now build the `u'` mu bound. I'll destructure `hp` first (via `case`, which handles nested patterns reliably).
