# Tree-0.0 · turn 20 · probe_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:31:47.820Z -->

**Intent:** `probe_tactic`  
**Payload:** `call (_: ={PIR.s}).`

---

I'm back to after `proc.` with the original postcondition `={PIR.s}` and 5 statements (init + while + 2 query calls). Now I need a better strategy.

Let me try `call (_: ={PIR.s}).` — this handles the last call (`r' <@ PIR.query(PIR.s')`) and preserves `={PIR.s}`. The postcondition of the residual goal should only need `={PIR.s}` (not `={PIR.s'}`).

Let me probe this.
