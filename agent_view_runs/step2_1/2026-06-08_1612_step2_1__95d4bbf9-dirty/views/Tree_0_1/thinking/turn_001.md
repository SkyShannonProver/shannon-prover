# Tree-0.1 · turn 1 · commit_tactic

<!-- session b1d56379-c118-4462-8adc-ddc4d1f41224 · 2026-06-08T23:16:42.926Z -->

**Intent:** `commit_tactic`  
**Payload:** `have hL : Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] = Pr[CCA_game(A, RealOrcls(StLSke(St))).main() @ &m : res].`

---

I'll start by reading the current workspace view to understand the proof state.

Let me read the followup and the source lemma file.

I'll read the source file to understand the lemma and its surrounding context.

Let me find the `step2_1` lemma and surrounding context.

This is a hard probabilistic reduction (CCA → CPA + forgery-event bound). Let me understand the modules involved.

Let me look at the key module definitions — CCA_CPA_Adv, St, StLSke, OChaChaPoly, and the imports.

`CCA_CPA_UFCMA` (line 742) is likely a generic theory with exactly this reduction lemma. Let me examine that clone and the surrounding context.

Let me find the `CCA_CPA_UFCMA` theory source — it likely contains the generic reduction lemma I need.

There's a generic lemma `CCA_UFCMA.CCA_CPA_UFCMA` whose RHS matches the goal exactly. Let me read the abstract theory section and the relevant module definitions.

The generic lemma's RHS matches the goal; only the LHS differs (`OChaChaPoly(IFinRO)` vs `StLSke(St)`). Let me read `OChaChaPoly`, the section header at 1023, and `IFinRO`.

Let me look at the `OpCC` theory header, `OCC`/`cc`/`get`, the two clones, and the section at 1023.

Now I understand the correspondence: `get gs = cc gs` (both `oget gs.[(n,c)]`), and both `OCC.gs` and `StLSke.gs` become `RO.m`. Let me verify `ChaChaPoly.kg` matches `OCC.kg`.

`ChaChaPoly.kg` and `OCC.kg` are identical (both sample `dkey`). Now let me read the outer section header (line 1023) to see what's declared about `A`.

I now understand the structure. The goal's RHS exactly matches the generic admitted lemma `CCA_UFCMA.CCA_CPA_UFCMA`; only the LHS scheme differs (`OChaChaPoly(IFinRO)` vs `StLSke(St)`), and those two are observationally equal (`get gs = cc gs = oget gs.[(n,c)]`, both `gs = RO.m`, both `kg` sample `dkey`). 

My plan: prove the LHS equality by `byequiv`, rewrite, then apply the generic lemma. Let me start by establishing the equality as a `have`.

I'll commit the first tactic establishing the LHS equality.
