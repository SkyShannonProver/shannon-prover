## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
h2: Pr[CCA_game(BNR_Adv(A), RealOrcls(ChaChaPoly)).main() @ &m : res] <=
    Pr[Split1.IdealAll.MainD(G8(BNR_Adv(A)),
                         SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish
       () @ &m : res] +
    Pr[Split1.IdealAll.MainD(G9(BNR_Adv(A)),
                         SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish
       () @ &m : res] +
    (Pr[Indist.Distinguish(D(BNR_Adv(A)), IndBlock).game() @ &m : res] -
     Pr[Indist.Distinguish(D(BNR_Adv(A)), IndRO).game() @ &m : res])
h3: Pr[Split1.IdealAll.MainD(G8(BNR_Adv(A)), SplitC2.RO_Pair(ROin, ROout)).distinguish
       () @ &m : res] =
    Pr[CPA_game(CCA_CPA_Adv(BNR_Adv(A)), EncRnd).main() @ &m : res]
h41: Pr[Split1.IdealAll.MainD(G9(BNR_Adv(A)), SplitC2.RO_Pair(ROin, ROout)).distinguish
        () @ &m : res] <=
     Pr[UFCMA(RO).distinguish() @ &m : res \/ UFCMA.bad2] +
     Pr[UFCMA(RO).distinguish() @ &m : UFCMA.bad1]
------------------------------------------------------------------------
Pr[CCA_game(BNR_Adv(A), RealOrcls(ChaChaPoly)).main() @ &m : res] <=
Pr[CCA_game(CCA_CPA_Adv(BNR_Adv(A)), EncRnd).main() @ &m : res] +
(Pr[Indist.Distinguish(D(BNR_Adv(A)), IndBlock).game() @ &m : res] -
 Pr[Indist.Distinguish(D(BNR_Adv(A)), IndRO).game() @ &m : res]) +
qdec%r * maxr pr_zeropol pr1_poly_out + qdec%r * pr1_poly_out
[437|check]>
```

## Opener — reduce the probability goal

**Goal shape:** a Pr-difference / distinguishing-advantage bound relating 14 `Pr[...]` terms

**Reduce with:**
- `apply (ler_trans <mid>)` / `rewrite` a `|·|` norm or `ler_add` step — an order/transitivity move that splits the `|Pr − Pr|` / sum bound into per-term obligations; this comes BEFORE any byequiv/byphoare
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound
- `rewrite (<a Pr (in)equality lemma> &m …)` — replace ONE `Pr[...]` term with an equal one; byequiv/byphoare reduce a single program, but this goal relates several Pr terms, so reduce them one at a time

**Unfoldable heads:**
- `rewrite /pr1_poly_out.` (unfolds `pr1_poly_out`)

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

_Need richer context? `inspect_context` topics: `goal_info` · `pr_bridge_routes` · `equiv_bridge_lemmas` · `lemma_hints` · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `have h41 := step4_1 &m.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/night_ccp_fable_l4np/l4_checked_action_surface/cc_conclusion/r01/2026-06-11_0152_conclusion/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/night_ccp_fable_l4np/l4_checked_action_surface/cc_conclusion/r01/2026-06-11_0152_conclusion/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/night_ccp_fable_l4np/l4_checked_action_surface/cc_conclusion/r01/2026-06-11_0152_conclusion/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/night_ccp_fable_l4np/l4_checked_action_surface/cc_conclusion/r01/2026-06-11_0152_conclusion/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
