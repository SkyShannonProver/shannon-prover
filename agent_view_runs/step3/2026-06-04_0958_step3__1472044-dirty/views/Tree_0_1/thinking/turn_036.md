# Tree-0.1 · turn 36 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:23:15.817Z -->

**Intent:** `commit_tactic`  
**Payload:** `conseq (equ_cc (p{1}.`1) mr0 ms0).`

---

`call` still rejects even with logical-variable arguments, so it's a procedure/lemma matching failure, not arguments. The L1 view hides the EC error. Let me search the run directory for any logged EC stderr from these rejected commits.

`call` rejects even with logical-variable args, so the procedures aren't matching the lemma. Rather than mine private transport files for the hidden error (against this profile's boundary), let me try applying `equ_cc` via `conseq` instead — a different matching path that will tell me whether the procedure-matching itself is the problem.
