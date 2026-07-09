# Tree-0.0 · turn 5 · inspect_context

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:32:09.839Z -->

**Intent:** `inspect_context`  
**Payload:** `call_site_options`

---

Let me check the full workspace view to see if the inline probe was accepted or rejected.

Both `inline *` and `inline PRPc.PseudoRP.fi` are rejected. Let me look at the call_site_options to understand how to handle the calls, or try the `call` tactic form. But actually, in phoare logic, the approach is different.

Let me think about what would work:
1. Maybe I should try `sp` first to process the prefix assignments
2. Or maybe I should try `wp` to process from the end
3. Or `conseq` to set up a simpler post

Actually, wait — for phoare goals, `inline` might need a different syntax. Let me check the call site options.
Maybe `inline` doesn't work in phoare context at all, so I should look at what call_site_options are actually available and try `sp` to handle the prefix assignments first.
