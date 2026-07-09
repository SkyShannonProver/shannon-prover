# Tree-0.0 · turn 9 · probe_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:26:06.504Z -->

**Intent:** `probe_tactic`  
**Payload:** `while (={PIR.s, j}).`

---

The error says "seq onsided: a pre and a post is expected". This means the `seq` tactic in "one-sided" mode (when programs are in sync) needs both a pre and post. The correct syntax for `seq` in pRHL with programs in sync might be different.

Actually, wait — "programs are in sync" means EasyCrypt is using a special one-sided representation. In this mode, standard two-sided pRHL tactics like `seq n1 n2: P` might not work. Instead, EasyCrypt might expect `seq n: (pre) (post)` or just different syntax.


Let me try specifying both a precondition and postcondition for the cut point, maybe something like `seq 2: (={PIR.s, j}) (={PIR.s, j}).` to satisfy what the one-sided mode is asking for.

Actually, I'm realizing that `proc` might be putting the programs into a mode where standard tactics like `inline` and `wp` don't work as expected — perhaps EasyCrypt treats identical procedures specially. Let me backtrack and try a different sequence: maybe `proc; while (={PIR.s, j}).` will work directly, or I could test `while` from the current state without the `proc` tactic first.
