# Tree-0.0 · turn 2 · inspect_context

<!-- session e60e6dbc-412b-42a6-ac10-5ce092bc8486 · 2026-06-09T18:50:34.119Z -->

**Intent:** `inspect_context`  
**Payload:** `pr_bridge_routes`

---

call_site_options didn't surface the bodies. Let me read the SigmaProtocol theory to understand the two game procedures.

Now I understand the full structure. This is a classic SHVZK proof:
- **gameReal**: samples w, r, e; transcript = (g^r, e, r+e·w)
- **gameIdeal**: samples w, r'(dead), e, z; transcript = (g^z·x^(-e), e, z), via simulate+verify(always true)+while(never loops)

The coupling is the bijection z = r + e·w (so g^r = g^(z−e·w) = g^z·x^(−e)). Let me check if the manager has a verified Pr bridge route first.
