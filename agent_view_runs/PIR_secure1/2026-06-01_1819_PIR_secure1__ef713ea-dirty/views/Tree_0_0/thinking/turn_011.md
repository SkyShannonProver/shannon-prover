# Tree-0.0 · turn 11 · probe_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:27:40.908Z -->

**Intent:** `probe_tactic`  
**Payload:** `call (_: true).`

---

Parse error on `sim / {i} {i}.`. The "programs in sync" mode is really limiting what tactics work. Let me step back and think about this differently.

The key issue is that after `proc.`, EasyCrypt puts the programs "in sync" because both sides have the same procedure (`PIR.main ~ PIR.main`). In this mode, many standard pRHL tactics don't work as expected.

Let me undo `proc.` and try a completely different opener. Instead of `proc.`, what about:

1. `byequiv (_: true ==> ={PIR.s}) => //.` — but this is the lemma itself, so it would be circular.


2. Start from the top-level equiv judgment and use `conseq` to change the postcondition.

Actually, let me look more carefully at how `PIR_secure2` handles this. It applies `proc.` followed by `inline *` to unfold all procedures, then uses `wp` to simplify the weakest precondition, maintains the loop invariant `={PIR.s', j}`, and applies a randomness argument to handle the case where the indices differ. But when I try `inline *` after `proc.` in my case, it fails — I need to figure out why that's happening.

Let me check if the issue is that the eval copy of the file differs from what I'm expecting. Looking at the actual source, `PIR_secure2` already has a complete proof without any admits, so it's a working reference. The proof structure shows the tactic sequence that should work, so I need to understand what's different about my setup.

The strange part is that `proc; inline *; wp` succeeds for `PIR_secure2` but `inline *` fails for `PIR_secure1` even though they're both equivalence proofs with identical program structure. This suggests either a version difference in EasyCrypt or something about how the "programs in sync" optimization behaves differently between the two cases.

Looking at the manager's response, it seems `inline *` was actually rejected by EasyCrypt without a clear error message, so I should try a different form of the inline tactic to see what works.

Let me consider a few alternatives: explicitly inlining on each side separately, using `cfold` to break the synchronization, or going back to `nosimpl proc` and building up from there. I'm also wondering if I should restart completely and try a fresh proof strategy from the top-level equivalence, possibly using a non-identity coupling like the one that worked for PIR_secure2. The issue is that `={i}` can't be proven from `true` since the inputs are arbitrary. Let me reconsider the whole approach: the claim states that for any two inputs, `PIR.s` ends up coupled, and the key insight is that `s` only gets modified when `b = true`, adding the same `j` on both sides. Since `b` is sampled identically with the coupling, both executions build identical `s` values. The problem is that after `proc.`, EasyCrypt synchronizes the programs in a way that creates a mismatch between what the coupling assumes and what the proof state requires.

I should try tactics that break this synchronization — either `symmetry` to reshape the representation, or more directly, `call (_: true).` to handle the final call with the trivial invariant.
