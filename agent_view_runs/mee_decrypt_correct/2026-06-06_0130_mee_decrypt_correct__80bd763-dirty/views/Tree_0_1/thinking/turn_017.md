# Tree-0.1 · turn 17 · commit_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:41:33.754Z -->

**Intent:** `commit_tactic`  
**Payload:** `auto.`

---

Now I have the initialization subgoal: `pre ==> true` with no program. This is trivially true. I should close it with `auto.` or `skip; auto.` or `trivial.`. Since there are no program statements, this is a `skip` goal, so I need `skip; auto.` or just `auto.`.

Wait, actually, looking at the goal, there are no program statements shown. In EasyCrypt, when there's no program, I need to use `skip` to convert it to a logical obligation. Then `auto` or `trivial` should close it since `post = true`.
Let me try `auto.` first.
