# Tree-0.0 · turn 5 · commit_tactic

<!-- session e8f72e76-a384-4fe6-8d81-b6f47e2ab598 · 2026-06-05T17:06:04.926Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv: DoubleQuery.bad => //.`

---

Let me read the actual EasyCrypt error message.

No detailed error in this profile. Let me look at how upto-bad `byequiv` is invoked elsewhere in the EasyCrypt corpus (non-target files are fine).

The corpus confirms the colon-form `byequiv : <bad_event>` (seen in non-target files `Two_perm_from_one.ec:450` and the CMAC `Perm3.ec`/`Simul3Perm.ec`). My explicit equiv-spec form was wrong — the upto-bad form takes just the bad event after a colon. Let me use it.
