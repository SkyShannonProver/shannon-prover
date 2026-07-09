# Tree-0.1 · turn 26 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:33:48.070Z -->

**Intent:** `probe_tactic`  
**Payload:** `wp; rnd; skip => /> /#.`

---

Now I need to prove the loop body preserves `={PIR.s, j}`. The loop body is:
```
b <$ {0,1}
if (j = i) {
    if (b) { PIR.s <- j :: PIR.s }
    else { PIR.s' <- j :: PIR.s' }
} else {
    if (b) { PIR.s <- j :: PIR.s; PIR.s' <- j :: PIR.s' }
}
j <- j + 1
```

The precondition is `={PIR.s, j} /\ j < N`.


To show the postcondition holds, I'll use the fact that `PIR.s` gets updated to `j :: PIR.s` exactly when `b = true`, and since `b` is coupled identically across both sides, the equality of `PIR.s` is preserved through the update. Then `j` increments equally on both sides, maintaining the invariant.
