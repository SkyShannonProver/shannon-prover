# Tree-0.0 · turn 24 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:12:31.086Z -->

**Intent:** `commit_tactic`  
**Payload:** `sp.`

---

The `call` tactic is refusing the `=1` spec on a `≤1` upper-bound goal. Let me look for the actual EasyCrypt error text in the full view to understand what it wants.

The `call` tactic doesn't accept this `≤1` upper-bound shape regardless of the spec. Let me try absorbing the head assignments first with `sp`, isolating the lone adversary call.
