# Tree-0.0 · turn 6 · commit_tactic

<!-- session d4771894-db82-4387-bd18-cccba31e1bb3 · 2026-06-06T23:00:23.913Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline *.`

---

All structural tactics are being rejected, which is odd. Let me independently test tactics against EasyCrypt directly (backend debugging on a scratch copy, not a prior proof) to find what works.

Standalone EC proves it with `proc; inline *; auto.` — so the proof is correct and the session is live (note `sp.` legitimately fails since the head is a call). The manager rejecting `inline` is the puzzle. Let me test whether `inline *.` errors when run as a separate step in standalone.

Standalone confirms `proc. inline *.` works (the only error is the expected "incomplete proof" at qed). So the manager session is rejecting a valid tactic. Let me retry `inline *.` once in case it was transient.
