# Tree-0.1.0 · turn 15 · undo_to_checkpoint

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:32:51.008Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `(none)`

---

I've now hit the real obstacle. Reading the post's `inv_cpa` obligation: it requires `lenc1 = lenc2`, i.e. `p{1}.\`1 :: BNR.lenc{1} = p{2}.\`1 :: BNR.lenc{2}`. From the current pre I have `BNR.lenc{1}=BNR.lenc{2}` (via `inv_cpa`) and `n{1}=p{1}.\`1`, `n{1}=n{2}` — giving `p{1}.\`1 = n{2}`. But I have **no** fact tying `p{2}.\`1` to `n{2}`. The original pre (before the replayed `seq 1 1`) had `p{1}=p{2}` (and `p0{1}=p{1}`, `p0{2}=p{2}`), but the seq's intermediate assertion `Q` dropped them, keeping only `p0{1}=p0{2}`. So `Q` is too weak and this subgoal is unprovable as cut.

The fix is to strengthen the `seq` cut to retain `p{1}=p{2}`. Let me get the checkpoint menu to rewind to that boundary.
