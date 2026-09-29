# Tree-0.0 · turn 15 · commit_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:28:42.302Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: true).`

---

Now I have 1 remaining goal. The current goal has:
- pre = true
- Statements 1-3 (init + while loop) + statement 4 (r <@ PIR.query(PIR.s))
- Post includes ={PIR.s'} and ={PIR.s}

I need to handle the remaining `r <@ PIR.query(PIR.s)` call. Let me use `call (_: true).` again to handle it. Then the loop + init should be left.
