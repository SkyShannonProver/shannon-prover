# Tree-0.0 · turn 6 · probe_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:32:29.339Z -->

**Intent:** `probe_tactic`  
**Payload:** `hoare.`

---

The inspect_context for call_site_options didn't return much info inline. Let me check the followup file.

Let me try a different approach. Instead of trying to inline (which is rejected), let me try to use `sp` to first process the straight-line prefix, then handle the loop. Actually, let me first try to look up what `PseudoRP.fi` and `MAC.verify` look like.

Actually, let me try a completely different approach. For phoare goals, the typical approach when we have calls is to use `ecall` or convert to Hoare logic first via `hoare`. Since the probability bound is `=1%r` and the procedure is deterministic, we should be able to convert to Hoare logic.
Since a phoare goal with bound `[=] 1%r` means the postcondition holds with probability 1, that's essentially Hoare logic. I could try `conseq` to simplify the form, or just switch directly to Hoare logic with `hoare`.
