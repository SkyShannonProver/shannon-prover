# Tree-0.0 · turn 20 · probe_tactic

<!-- session 00419e7b-22c2-477c-b7b6-2ff3591b0428 · 2026-06-10T21:46:38.665Z -->

**Intent:** `probe_tactic`  
**Payload:** `byequiv (_: ={glob A} ==> (exists (c:ciphertext), c \in Mem.lc /\ dec StLSke.gs Mem.k c <> None){1} => res{2}).`

---

Goal 1 (`A <= C`) is fully discharged via `UFCMA_genCC`. Now the remaining goal 2 is the forgery bound `B <= D`. Let me study the analogous reduction idiom in the imported `ske.ec` theory before composing.

Now goal 2: the forgery bound `Pr[UFCMA(A,St): forge_event] <= Pr[UFCMA_poly: res]`. Key facts: `UFCMA_genCC` gives `={Mem.lc} /\ StLSke.gs{1}=RO.m{2}`, the op `dec`/`genpoly1305` ignore `k` (via `get gs k n c = oget gs.[(n,c)]`), and `UFCMA_poly` runs the same game then a forge-detection loop. Let me set up the byequiv with the implication post.
