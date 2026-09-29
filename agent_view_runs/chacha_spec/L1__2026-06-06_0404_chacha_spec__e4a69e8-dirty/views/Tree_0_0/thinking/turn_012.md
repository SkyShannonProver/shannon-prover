# Tree-0.0 · turn 12 · commit_tactic

<!-- session 7d9e4e8f-9d68-4e90-9a25-30821d7062c9 · 2026-06-06T11:12:59.979Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: true ==> res = cc OCC.gs k n c).`

---

All inline forms fail with no detail. Let me read the followup file for the actual EasyCrypt error message.

The L1 profile hides the EC error text, and inline is consistently rejected (likely EC won't inline a functor applied to the abstract declared module `I`). I'll handle the call with the `call` tactic and an anonymous phoare spec for `cc` instead.
