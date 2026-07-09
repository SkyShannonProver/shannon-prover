# Tree-0.1 · turn 16 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:48:41.238Z -->

**Intent:** `commit_tactic`  
**Payload:** `by exfalso.`

---

The current goal is:

```
pre = !true /\ arg{1} = arg{2} /\ (Game1.r{2} \in Log.qs{2})

    Log(LRO).o ~ Log(LRO).o 

post = true
```

The precondition is `!true /\ ...` which is `false /\ ...` = `false`. So this goal is trivially true (from `false`, anything follows).

Let me prove it with `proc; auto` or `by exfalso` or `by move=> &1 &2 [#]`.


Since the precondition reduces to false, I can discharge this immediately with `exfalso` or a simple move tactic that handles the contradiction.
