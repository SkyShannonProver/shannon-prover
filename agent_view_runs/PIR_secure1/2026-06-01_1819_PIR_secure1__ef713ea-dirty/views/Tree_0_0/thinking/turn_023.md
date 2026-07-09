# Tree-0.0 · turn 23 · commit_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:32:35.402Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: ={PIR.s}).`

---

Now I have 1 goal remaining, with the init + while loop + one remaining call `r <@ PIR.query(PIR.s)`. Let me handle the second call the same way, then handle the while loop.

The postcondition should now include `={PIR.s}` properly framed. Let me do `call (_: ={PIR.s}).` for the remaining call, then `auto.` for the call spec, and then we should have just the init + while loop with `={PIR.s}` postcondition.

Let me commit `call (_: ={PIR.s}).` and `auto.` to handle the remaining query call.
