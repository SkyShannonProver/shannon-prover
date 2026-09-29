# Tree-0.0 · turn 14 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:11:07.411Z -->

**Intent:** `commit_tactic`  
**Payload:** `skip.`

---

Now all samplings have been coupled. The remaining goal is a pure logical formula with no programs left. I can see `pk_L = g ^ sk0L` and `pk_L = g ^ sk0L` which is trivially true! The postcondition should be mostly tautological now since `sk0{1} = x{2}` (both coupled to `sk0L`) and `y{1} = y{2}` (both coupled to `yL`).

Now I need `skip.` to discharge the empty program, and then some logic tactic to close the remaining formula. Let me try `skip.` first.
