# Tree-0.0 · turn 26 · commit_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:08:18.748Z -->

**Intent:** `commit_tactic`  
**Payload:** `case (DoubleQuery.bad{2}).`

---

The `f` bodies are exposed:
```
if (x ∈ qs) { bad<-true }        if (x ∈ qs) { bad<-true }
r <@ PRFi.f(x)                   r <@ Sample.f(x)
qs <- qs `|` fset1 x             qs <- qs `|` fset1 x
```
The leading `if` can flip `bad`, so I case-split on `bad{2}` to cleanly separate the "already bad" (divergent, lossless) branch from the main `!bad{2}` (synchronized) branch. Committing the case split.
