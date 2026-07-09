# Tree-0.0 · turn 4 · commit_tactic

<!-- session 9c846476-96bc-4564-94eb-a9ec19803719 · 2026-06-09T00:00:09.535Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ->: Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] = Pr[CCA_game(A, RealOrcls(StLSke(St))).main() @ &m : res].`

---

Exact signature obtained. The generic lemma's RHS matches our goal's RHS exactly; only the LHS differs (`OChaChaPoly(IFinRO)` vs `StLSke(St)`). The `valid_key` hyp degenerated to `hoare[St.kg: true ==> true]` (trivial). Let me read the game/oracle definitions in ske.ec to write the LHS-normalizing byequiv.

Now I understand the structure. `CCA_game(A, RealOrcls(SKE)).main` runs `RealOrcls(SKE).init(); b <@ A(RealOrcls(SKE)).main()`. The only difference between LHS and the generic lemma's LHS is the SKE module: `OChaChaPoly(IFinRO)` vs `StLSke(St)`, which compute the same enc/dec (the clone defines `enc`/`dec` ops matching OChaChaPoly's inline bodies, and `cc gs = get gs = oget gs.[(n,c)]`).

Let me commit the LHS-normalizing rewrite.
