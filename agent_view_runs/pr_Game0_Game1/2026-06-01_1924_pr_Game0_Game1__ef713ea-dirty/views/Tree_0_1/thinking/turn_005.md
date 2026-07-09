# Tree-0.1 · turn 5 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:39:28.255Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: ={glob Log, glob LRO}).`

---

The tactic was rejected. Let me read the full workspace view to see the error message.

The error doesn't give me details about WHY it was rejected. Let me check the latest_followup.md for more info.

The error message doesn't contain specific details about why the tactic was rejected. The "upto bad" call syntax might be different in this version of EasyCrypt.

Let me think about alternative approaches:

1. The `call` with the comma-separated "upto bad" syntax might not exist, or might have different syntax.
2. Maybe I need a `wp` before the `call`.
3. Maybe the issue is that `eq_except` is not directly available, or the `pred1` form isn't recognized.

Let me try a different approach. Instead of the "upto bad" call, let me try to:


- Either completely restart with a different proof strategy
- Or experiment with alternative `call` syntax variations

I could try passing just the global state equality without the "upto bad" modifier to see if that syntax is accepted, or I could explore different ways to express the predicate about the oracle state and log entries using whatever syntax this version of EasyCrypt supports.

Let me start simple and test whether `call` works at all with a minimal invariant, then build from there if needed. level and try to structure the proof differently.

What if I use `seq` to split at the encryption boundary, and then handle each part separately? For the first part up to and including encryption, I'd establish an invariant relating the game states, then for the second part with the a2 call, I'd need to prove equivalence with just that function invocation on both sides—but I'm running into the same issue with how to handle the `call`.

Let me step back and consider abandoning `byequiv` entirely. For the goal `Pr[G0 : res] <= Pr[G1 : res] + Pr[G1 : bad]`, I could try establishing a probability bound directly by relating the two games through a hybrid argument, though I'd need to be careful about what variables actually exist in each game context. Maybe the `call` issue is actually simpler than I'm making it—let me reconsider what's really blocking me here.
