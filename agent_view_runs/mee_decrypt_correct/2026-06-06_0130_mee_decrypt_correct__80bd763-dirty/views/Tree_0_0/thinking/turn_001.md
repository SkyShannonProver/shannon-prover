# Tree-0.0 · turn 1 · probe_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:30:53.905Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc.`

---

Let me analyze the proof goal for `mee_decrypt_correct`. This is a `phoare` (probabilistic Hoare) lemma about the correctness of MEE decryption.

The goal is:
```
_mk: mK
_ek: block
_c: block list
------------------------------------------------------------------------
pre = key = (_ek, _mk) /\ c = _c

    MEE(PRPc.PseudoRP, MAC).dec 
    [=] 1%r

post = res = mee_dec AESi hmac_sha256 _ek _mk (head witness _c) (behead _c)
```

This phoare statement asserts that the MEE decryption procedure, given the precondition that the key and ciphertext are bound to specific values, produces a result matching the functional specification `mee_dec` with probability exactly 1. Since decryption is deterministic with no randomness involved, I should be able to prove this by unfolding the procedure definition and verifying it matches the spec.

Now I'm going to enter the procedure body using `proc.` and work through the proof step by step, then load the MCP tool schema to help with the formal verification.
```

Now let me start by probing `proc.` to enter the procedure body and see what the decryption procedure looks like.
