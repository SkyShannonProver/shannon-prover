# Tree-0.1 · turn 1 · probe_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:30:49.049Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc.`

---

Let me analyze the proof goal for `mee_decrypt_correct`. This is a `phoare` (probabilistic Hoare) lemma about the correctness of MEE decryption.

The goal is:
```
pre = key = (_ek, _mk) /\ c = _c

    MEE(PRPc.PseudoRP, MAC).dec 
    [=] 1%r

post = res = mee_dec AESi hmac_sha256 _ek _mk (head witness _c) (behead _c)
```

This is a phoare judgment saying that `MEE(...).dec` with the given precondition produces the given postcondition with probability exactly 1 (i.e., it's deterministic).
I'll start by unfolding the procedure definition with `proc.` to see what the decryption logic looks like, then work through the verification conditions using tactics like `wp`, `sp`, and `auto`.
