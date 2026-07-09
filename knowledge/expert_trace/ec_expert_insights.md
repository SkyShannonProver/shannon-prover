# EasyCrypt Expert Insights

**Date:** 2026-04-12
**Source:** Discussion with EasyCrypt authors

---

## How Experts Prove Hard Lemmas: Bottom-Up Invariant Discovery

### The Pattern

Hard EasyCrypt proofs (game-based cryptographic reductions) follow a consistent pattern:

1. **Guess an invariant** that relates the state of two games
2. **Decompose into oracle subgoals** — each oracle must preserve the invariant
3. **Try each oracle** — if one fails, the invariant is wrong
4. **Refine the invariant** based on what the failing oracle needs
5. **Retry** until all oracles pass

This is "bottom up" because the expert starts from the oracle-level details and works up to the correct invariant, rather than trying to get the invariant right on the first attempt.

### Concrete Example: Hashed ElGamal (es0_Gb)

**Game ES0**: ElGamal encryption with a hash function H
**Game Gb**: Same structure but replaces H with a random function

The equivalence proof:

```
Step 1: Set up the equivalence framework
  byequiv => //; proc.

Step 2: Guess an initial invariant
  "The hash tables agree on all queried points,
   AND the secret key is the same,
   AND the adversary's view is identical"
  
  Formally: ={glob A, x, pk} /\ (forall q, H{1}.[q] = H{2}.[q])

Step 3: Decompose into oracle subgoals
  call (_: invariant).
  
  This creates ONE SUBGOAL PER ORACLE:
  - Hash oracle: prove invariant preserved when adversary queries H
  - Choose oracle: prove invariant preserved when adversary picks messages
  - Guess oracle: prove invariant preserved when adversary guesses
  - Encryption: prove invariant preserved during encryption

Step 4: Try each oracle
  - Hash oracle:    CAN prove ✓
  - Choose oracle:  CAN prove ✓
  - Guess oracle:   CAN prove ✓
  - Encryption:     CANNOT prove ✗
    The invariant doesn't capture that H(g^xy) is replaced by a
    random value in Gb. The subgoal asks us to show the ciphertext
    is identical, but ES0 uses H(g^xy) while Gb uses a fresh random
    value — these are different unless the invariant accounts for it.

Step 5: Refine the invariant
  Add: /\ (g^(x*y) \notin dom H{1} => Gb uses random for that point)
  
  This captures the key difference: on unqueried points, Gb's
  "hash" output is random instead of H-computed.

Step 6: Retry all oracles with refined invariant
  All pass ✓ — proof complete.
```

### The Critical Ability: Detecting Unprovable Subgoals

The most important expert skill is **quickly recognizing when a subgoal is unprovable** with the current invariant, rather than spending time trying different tactics.

An expert looks at a failing oracle subgoal for 30 seconds and says:
> "This is unprovable because the invariant doesn't distinguish H from
> the random function. I need to go back and change the invariant."

A novice (or our LLM prover) would:
- Try `smt()` → fails
- Try `auto` → fails
- Try `rewrite` variations → fails
- Spend 5-10 minutes before giving up

The distinction is:
- **"I can't prove this because I'm using the wrong tactic"** → execution problem, try different tactics
- **"This is genuinely unprovable with the current invariant"** → strategy problem, go back and change the invariant

### The Up-to-Bad Variant

A related pattern for probability bounds (not just equivalence):

```
1. Define a "bad event" (e.g., random oracle collision)
2. Prove Game0 and Game1 are IDENTICAL except when bad occurs
3. Bound Pr[bad]
4. Conclude: |Pr[Game0] - Pr[Game1]| <= Pr[bad]
```

This uses `eager` tactics and the same oracle decomposition. Each oracle must preserve:
- The games agree on all state (main invariant)  
- The bad flag is correctly maintained (bad event invariant)

If an oracle subgoal fails, it might mean:
- The bad event definition is wrong (too narrow or too broad)
- The invariant doesn't capture some state that differs between games
- The oracle itself has a genuine difference that needs to be accounted for

---

## Implications for Our Architecture

### What We Have

- **Strategy vs execution distinction**: Plan phases tagged as strategy or execution. Tree prover branches on strategy failures, retries on execution failures.
- **Tree prover**: When a prover gets stuck, spawns a child at the last branch point. Children get parent's goal state and shared discoveries.
- **KB patterns**: `self_transitivity_bijection`, `up_to_bad_eq_except`, and other structural patterns.

### What We're Missing

1. **Unprovable subgoal detection**: Our provers can't distinguish "wrong tactic" from "unprovable with this invariant." They waste time trying tactics on unprovable subgoals instead of going back to refine the invariant.

2. **Invariant refinement loop**: Experts iterate: guess invariant → try oracles → refine → retry. Our provers try ONE invariant and give up if it doesn't work. The tree prover could help — a child could be spawned that goes back to the invariant choice and tries a different one.

3. **Oracle-level progress tracking**: Experts think "3 out of 4 oracles work, only the encryption oracle fails." Our provers don't track which oracle subgoals succeeded vs failed — they just see "proof not done."

4. **Bottom-up strategy in KB**: The KB has patterns for individual tactics but not for the iterative invariant-discovery workflow. A KB entry describing "how to discover the right invariant through oracle-by-oracle testing" would be valuable.

### Potential Improvements

1. **Add a "try each oracle" mini-tool**: After `call (_: invariant)`, enumerate the oracle subgoals and try to close each one independently. Report which ones succeed and which fail. This gives the prover (and the tree spawner) targeted information about where the invariant is insufficient.

2. **Invariant refinement as a tree branch**: When the prover gets stuck on an oracle subgoal, instead of trying more tactics, branch back to the `call` tactic and try a different invariant. The negative signal should be: "the encryption oracle is unprovable because the invariant doesn't capture X."

3. **KB pattern for invariant discovery**: Add a pattern that describes the bottom-up workflow: "After `call`, if an oracle subgoal is unprovable for >2 minutes, the invariant is likely wrong. Go back to the `call` and strengthen the invariant to account for the failing oracle's specific behavior."

4. **Prover prompt guidance**: Tell the prover: "When you use `call (_: invariant)` and a subgoal seems unprovable, don't spend more than 2 minutes on it. Instead, analyze WHY it's unprovable and refine the invariant."
