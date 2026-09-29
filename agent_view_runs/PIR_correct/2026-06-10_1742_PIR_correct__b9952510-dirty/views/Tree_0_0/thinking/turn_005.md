# Tree-0.0 · turn 5 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:45:03.017Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc; inline *; wp; sp.`

---

Now into the procedure. I'll inline the two `query` calls (each just returns the XOR-sum), absorb the tail with `wp`, and the prefix with `sp`, to expose the while loop. Let me probe this chain.
