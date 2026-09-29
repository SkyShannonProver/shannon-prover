## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
h1: Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] -
    Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] =
    Pr[Indist.Distinguish(D(A), IndBlock).game() @ &m : res] -
    Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res]
h2: Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] <=
    Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() @ &m : res] +
    Pr[UFCMA(A, St).main() @ &m :
       exists (c : ciphertext),
         (c \in Mem.lc) /\
         dec StLSke.gs Mem.k c <> None<:nonce * associated_data * bytes>]
h3: Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() @ &m : res] +
    Pr[UFCMA(A, St).main() @ &m :
       exists (c : ciphertext),
         (c \in Mem.lc) /\
         dec StLSke.gs Mem.k c <> None<:nonce * associated_data * bytes>] <=
    Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main
       () @ &m : res] +
    Pr[UFCMA_poly(A, FinRO).main() @ &m : res]
------------------------------------------------------------------------
Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] <=
Pr[Split1.IdealAll.MainD(G8(A), RO_Pair(I1.RO, I2.RO)).distinguish() @ &m :
   res] +
Pr[Split1.IdealAll.MainD(G9(A), RO_Pair(I1.RO, I2.RO)).distinguish() @ &m :
   res] +
(Pr[Indist.Distinguish(D(A), IndBlock).game() @ &m : res] -
 Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res])
[312|check]>
```

## Opener — reduce the probability goal

**Goal shape:** a Pr-difference / distinguishing-advantage bound relating 16 `Pr[...]` terms

**Reduce with:**
- `apply (ler_trans <mid>)` / `rewrite` a `|·|` norm or `ler_add` step — an order/transitivity move that splits the `|Pr − Pr|` / sum bound into per-term obligations; this comes BEFORE any byequiv/byphoare
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound
- `rewrite (<a Pr (in)equality lemma> &m …)` — replace ONE `Pr[...]` term with an equal one; byequiv/byphoare reduce a single program, but this goal relates several Pr terms, so reduce them one at a time

**Unfoldable heads:**
- `rewrite /dec.` (unfolds `dec`)

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

_Need richer context? `inspect_context` topics: `goal_info` · `pr_bridge_routes` · `equiv_bridge_lemmas` · `lemma_hints` · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `have h3 := step2_2 &m.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/night_step2_fable_l4np/l4_checked_action_surface/cc_step2/r01/2026-06-11_0220_step2/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/night_step2_fable_l4np/l4_checked_action_surface/cc_step2/r01/2026-06-11_0220_step2/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/night_step2_fable_l4np/l4_checked_action_surface/cc_step2/r01/2026-06-11_0220_step2/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/night_step2_fable_l4np/l4_checked_action_surface/cc_step2/r01/2026-06-11_0220_step2/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
