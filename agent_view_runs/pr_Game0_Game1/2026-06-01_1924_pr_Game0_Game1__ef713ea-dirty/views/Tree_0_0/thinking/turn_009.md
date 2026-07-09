# Tree-0.0 · turn 9 · commit_tactic

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:37:41.164Z -->

**Intent:** `commit_tactic`  
**Payload:** `sim.`

---

Good, the `seq` was accepted. Now I have 5 remaining goals. The first one is the prefix subgoal. Let me read the full view.

Good. The first subgoal is the prefix:

Left:
```
Log(LRO).init()
kp <$ dkeys
(pk, sk) <- kp
(m0, m1) <@ A(Log(LRO)).a1(pk)
b <$ {0,1}
```

Right:
```
Log(LRO).init()
(pk, sk) <$ dkeys
(m0, m1) <@ A(Log(LRO)).a1(pk)
b <$ {0,1}
```

Pre: `(glob A){1} = (glob A){2} /\ LRO.m{1} = LRO.m{2} /\ Log.qs{1} = Log.qs{2}`


Post: `(glob A){1} = (glob A){2} /\ LRO.m{1} = LRO.m{2} /\ Log.qs{1} = Log.qs{2} /\ pk{1} = pk{2} /\ sk{1} = sk{2} /\ m0{1} = m0{2} /\ m1{1} = m1{2} /\ b{1} = b{2}`

Both sides execute identically here—the only difference is that the left inlines the keygen step while the right keeps it separate, but they produce the same values across all variables.

I need to work through this with a combination of tactics: `call` for the identical logging initialization, `rnd` to handle the key generation where the left side uses a different variable structure than the right, and `wp` for the deterministic assignment that follows. The tricky part is remembering that in EasyCrypt's pRHL, `call` works backwards from the end of the program, while `wp` also processes assignments from the end, so I need to be careful about the order of operations and potentially use `sp` if I need to work forward from the beginning instead.

Let me try using `sim` to see if it can automatically handle this, since the two programs are structurally very similar—the only real difference is how the keys are generated and destructured. If that doesn't work, I might need to manually guide the proof with a sequence of tactics like `wp` to work backwards through the boolean assignment, then `call` for the adversary invocation, and so on. sampling and then handle the rest. The simplest approach might be to use a tactic that samples, does weakest precondition reasoning, then calls with a postcondition about the global state. But that's getting unwieldy, so let me try just `sim` or `auto` to see if they can handle the structural differences between the two programs.

The issue is that the left side has an intermediate binding `kp <$ dkeys; (pk,sk) <- kp` while the right side directly does `(pk,sk) <$ dkeys`, which are semantically equivalent but syntactically different. The `sim` tactic might be smart enough to recognize this equivalence, or I could try more aggressive tactics like `swap` or `sp` to reorder statements. Let me start by attempting a direct call tactic that focuses on the final procedure invocation and the relevant global state. Writing proof tactics... Trying different tactic approaches to handle the structural mismatch in the keygen — `wp` alone won't work since it only processes deterministic code, not the random sampling. Let me attempt `sim` first to see if it can absorb the initial identical parts, or fall back to a combination like `wp; rnd; call` with the right postcondition to handle the oracle calls that will inevitably arise. I'm realizing that `call` won't work on the final `b <$ {0,1}` statement since that's a sampling operation, not a procedure call. Let me start with `rnd` to handle that first, then work through the rest of the proof systematically.
