# Tree-0.0 · turn 17 · probe_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:41:08.406Z -->

**Intent:** `probe_tactic`  
**Payload:** `seq 1 : (padded = cbc_dec AESi _ek (head witness _c) (behead _c) /\ ek = _ek /\ mk = _mk /\ p = None).`

---

The goal text says "unchanged" — let me check if wp was accepted or rejected.

`wp` also rejected. Let me think about why. In phoare context, `wp` should work backwards from the end absorbing deterministic assignments. But maybe EasyCrypt's `wp` can't cross the `if` block because the `if` block contains a call to `MAC.verify`.

Wait, actually — `wp` in the phoare context might not be able to start absorbing because the LAST statement involves a call (`b <@ MAC.verify(mk, p', t)` inside the `if` block). Since `wp` processes from the end and stops at calls/loops, and the last non-assignment statement is inside the `if` block which contains a call, `wp` might not be able to process anything.
 
Looking at the structure more carefully: after `sp.` there's a while loop with a call inside, then an assignment, then an if block with a call. Since `wp` works backwards from the end and hits that call in the if block immediately, it can't absorb anything. I need to handle the calls first — maybe I can use `seq` to split at the boundary between the while loop and what comes after, then tackle each part separately.

Or I could try using `call` directly with a Hoare spec on the last call in the remaining code, which would be `MAC.verify`. The syntax would be something like specifying what the call should establish about the result.

But there's a structural problem — `MAC.verify` is nested inside an `if` block, not at the top level, so tactics like `call` or `ecall` might not work as expected. Let me check if there are existing Hoare or pHoare lemmas in the PseudoRP module definition that I can leverage instead.

Let me look for the PseudoRP module type definition. It should be in one of the PRP-related files. Since the `MAC_then_Pad_then_CBC.eca` does `require (*..*) PRP`, let me search for PRP in the EasyCrypt standard library.

Actually, let me check the MEE-CBC local files first. The `PseudoRP` clone is done inside `MAC_then_Pad_then_CBC.eca`:
```
clone import PseudoRP as PRPc with
  type K  <- eK,
  op   dK <- d_eK,
  op   p  <- P,
  op   pi <- Pi
```

So `PseudoRP` is a theory from the PRP library. The key thing is that `PRPc.PseudoRP.fi` is a concrete module procedure that just returns `pi k x` where `pi = Pi = AESi`. Now I need to figure out where the issue lies in how this is being used.

In the phoare context, tactics like `inline`, `wp`, and basic `call` aren't working for handling procedure calls. Let me explore different approaches. I could try `auto` to see if it handles simple deterministic code, or use `conseq` to reduce the phoare bound and split the proof into more manageable pieces.

The key insight is that `conseq` can decompose the goal into a regular hoare part and a losslessness part. For the hoare portion, I can use `proc; inline *; wp; skip; smt(...)` since `inline` works in hoare context. For the losslessness part, I'd need a different tactic strategy. Let me try `conseq` explicitly with the proper EasyCrypt syntax to see if this decomposition helps.

Actually, I'm realizing the real issue: `inline` doesn't work in phoare context due to EasyCrypt limitations, `wp` can't handle calls, and I need to try the `call` tactic instead. The code structure has a while loop with calls inside, so `call` might need to target the last call specifically.

In EasyCrypt, `call` works on the final instruction if it's a call, but if the last instruction is an `if` block, I need to handle that first. So my approach should be to process the `if` block with a conditional tactic, then handle the call inside it. For the while loop before the `if`, I'll need to use the `while` tactic and establish a loop invariant.

Let me reconsider using `exlim` to extract the result of the call, or look more carefully at the available phoare tactics. The key ones are `proc` to unfold procedures, `sp` and `wp` for pushing assignments, `while` for loops, `call` for procedure calls at the end, `ecall` for explicit phoare specs, and `skip` to finish.

I think the real issue is that I need to use `seq` to split the code at the right positions and process each piece separately. Let me try splitting after the while loop and unpad assignment with a `seq` tactic that captures the intermediate state. Refining the invariant to focus on what matters for the suffix—I need to track that the encryption key and MAC key match their initial values, and that `padded` contains the decrypted ciphertext, while `p` remains `None` at the loop's end. Continuing through the unpad operation, `pt` gets bound to the result, and then I'm checking whether it's None or contains a valid message-tag pair. If unpad succeeds, I extract the message and tag, verify the HMAC matches, and set `p` to either the message or None depending on whether the MAC check passes. If unpad fails, `p` remains None.

This matches exactly what `mee_dec` does, so the `seq 1` approach should work. I'm setting up a phoare `seq` cut with the postcondition that captures the state after decryption: the padded ciphertext decrypted, the encryption and MAC keys preserved, and `p` still None before the unpad operation.
