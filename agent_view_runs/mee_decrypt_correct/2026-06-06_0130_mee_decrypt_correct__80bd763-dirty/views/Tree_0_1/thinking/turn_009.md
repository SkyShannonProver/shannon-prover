# Tree-0.1 · turn 9 · commit_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:35:16.894Z -->

**Intent:** `commit_tactic`  
**Payload:** `sp.`

---

Let me check the full result of the wp probe.

`wp.` was also rejected. Interesting. So after `proc.`, both `inline *` and `wp.` are rejected, but `sp.` is accepted.

Let me think about why. In phoare mode after `proc.`, the program starts with assignments. `wp.` typically works backward from the postcondition, but in phoare mode, it might not work directly because the program has to start processing from the beginning (at least the assignments). `sp.` works forward, which is what's expected.

Actually wait, I think the issue might be different. In EasyCrypt, after `proc.`, the phoare judgment has both a program and a bound `[=] 1%r`. The `wp` tactic in phoare mode might have different behavior. Let me think...
 
I'll go with `sp.` since it's working and move forward from there to tackle the while loop and remaining code.
