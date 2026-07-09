# Tree-0.1 · turn 12 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:27:07.539Z -->

**Intent:** `probe_tactic`  
**Payload:** `sim (: true ==> ={PIR.s}).`

---

`inline *.` was genuinely rejected by EasyCrypt. So `inline *` truly doesn't work here. This confirms that the programs are in sync and there's nothing to inline — EasyCrypt already inlined everything or treats concrete procedure calls differently when programs are in sync.

Let me try a different approach. Maybe I need to use `conseq` to strengthen the postcondition to something `sim` can handle, minus the `i` equality. Or I should use `sim` with a specific relation.

Actually, in EasyCrypt, there's a variant of `sim`: 
```
sim /= : (R).


```

or
```
sim (_: R).
```

Where R is the relation to prove. Maybe I can use:
```
sim / ={PIR.s}.
```

This might tell `sim` to prove only `={PIR.s}` equality, not everything.

Let me look at `sim`'s forms. Actually, I know from EasyCrypt documentation that `sim` can take arguments:

- `sim.` — proves the relation by syntactic similarity, inferring equalities
- `sim / E.` — `sim` modulo specification E (drops the need for equality on certain variables)
- `sim (_: post).` — spec

I'm exploring different variants of the `sim` tactic that might let me specify which equalities to prove, potentially using modulo specifications or custom relations to avoid the problematic `i` equality constraint. I'm trying the explicit form `sim (: true ==> ={PIR.s}).` to specify both the precondition and postcondition directly, though I'm uncertain whether EasyCrypt expects the precondition argument or uses the current one by default. Let me test a few variations to see which syntax the tactic accepts.
