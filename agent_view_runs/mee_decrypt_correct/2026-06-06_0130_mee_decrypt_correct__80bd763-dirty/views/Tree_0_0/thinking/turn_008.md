# Tree-0.0 · turn 8 · probe_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:33:27.557Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline PseudoRP.fi.`

---

The lookup failed. Let me try looking up just `PseudoRP` or look at the source file to understand the module structure. Let me also try looking at the MAC_then_Pad_then_CBC clone to understand the module structure.

Actually, let me look at the source file to find where `PseudoRP` is defined. The clone is `MAC_then_Pad_then_CBC as MEEt`, so `PRPc` is likely a sub-theory within that clone. Let me look at the MEEt clone structure.

Actually, let me try a different approach. Instead of looking up symbols, let me try to directly work with the proof. The key insight is:
This is a phoare `[=] 1%r` goal where the procedure is deterministic with no sampling. The calls are to `PseudoRP.fi` which applies the cipher, and `MAC.verify` which checks the authentication tag. For a phoare proof, I need to use `sp` for the straight-line prefix, handle the loop with a loop invariant and variant, use `call` or `ecall` for the procedure calls within the loop, and then process the suffix.

Actually, I'm reconsidering the approach. I could use `conseq` to reduce this to a hoare triple plus a losslessness goal, which would split the proof into two parts. But I need to verify whether the procedures are lossless first. Let me look at the `mee_encrypt_correct` phoare in the file for clues about the pattern, since both are phoare goals. The procedure has assignments, a while loop with a call to `PseudoRP.fi` inside, and an if block with a call to `MAC.verify` inside. For the phoare `[=] 1%r`, I need to show that the probability is exactly 1.

Since there's no randomness in the body, this should be straightforward. For the `[=] 1%r` bound with no sampling, I'm thinking `conseq` might establish a weaker phoare, or maybe `wp` first since it processes deterministic assignments backwards. Let me try `sp` to handle the initial assignments before the loop, or maybe `wp` directly since it works backwards from the end but can't cross calls or loops. I'm also considering `ecall` in recent EasyCrypt, which can handle procedure calls in a phoare context.

Actually, the issue might be simpler—let me try inlining the procedure directly without worrying about side specifiers, since phoare only has one side. I'll experiment with different name resolution approaches for the inline tactic.
