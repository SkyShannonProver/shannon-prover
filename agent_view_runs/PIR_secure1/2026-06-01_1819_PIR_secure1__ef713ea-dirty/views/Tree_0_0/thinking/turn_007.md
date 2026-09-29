# Tree-0.0 · turn 7 · probe_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:25:07.216Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline PIR.query.`

---

`sp 2.` was rejected with "expecting a goal of the form: hoare[S], phoare[S]" — that means `sp` only works for hoare/phoare, not pRHL. That makes sense.

OK, let me think about what pRHL tactics are available for consuming the initialization:

1. `seq 2 2: (={PIR.s, PIR.s', j}).` — cut after the first 2 statements with intermediate condition
2. `while (={PIR.s, j}).` — but this might not work if while isn't the first statement


3. `call` — to handle the procedure calls from the back
4. `sim` with parameters

Actually, in EasyCrypt pRHL, the `while` tactic works on the outermost while loop regardless of what comes before it. If there are assignments before the while, they become part of the initialization subgoal. So `while (={PIR.s, j}).` could work! But there are statements after the while loop too (the query calls), which means `while` would split this into a loop body preservation goal and a post-loop goal with the query calls still in the code.

The structure of `while I` in pRHL is more nuanced than I initially thought. It creates a subgoal for the loop body (`I /\ guard ==> I`), but I'm still working through exactly how the pre-loop initialization and post-loop code interact with the tactic. The pre-loop assignments likely become part of establishing the invariant, and then the post-loop code continues after the loop is handled.

Rather than getting stuck on the theory, I should just experiment with the actual syntax. I'm going to try using `sim` with an explicit invariant specification like `sim (: ={PIR.s, j}).` to see if that lets the tactic handle the equivalence without needing to track `i` separately. If that doesn't work, I might need to try variations like `sim / {i} (: ={PIR.s, j}).` to see what EasyCrypt accepts. I'm trying to recall the exact EasyCrypt syntax for the `sim` tactic with variable exclusions — it should let me specify which variables to ignore on each side and provide a loop invariant, so I can exclude `i` and `r` from the equality requirements while keeping `PIR.s` and `j` synchronized. I'm trying different tactic approaches to get past the initialization and loop structure. The PIR_secure2 proof uses `proc; inline *; wp` followed by a while loop with specific coupling, but my `inline *` is failing, so I need to explore alternatives like `inline{1} PIR.query` or restart the proof entirely with a different strategy like `sim` with the right invariant.

Writing proof tactics...
