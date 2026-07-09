## 🎯 Current Goal
```
Current goal

Type variables: <none>

A(O : RCPA_Oracles) : RCPA_Adversary{-PRP, -PRPi, -RCPA_Wrap, -PRFi, -Compute, -QueryBounder}
&m: {}
A_run_ll: forall (O <: RCPA_Oracles{-A}),
            islossless O.enc => islossless A(O).distinguish
QBA_ll: forall (O <: RCPA_Oracles{-QueryBounder(A)}),
          islossless O.enc => islossless QueryBounder(A, O).distinguish
hmu: 0%r <= mu1 dBlock witness<:block>
hn: 1 <= q * ell
------------------------------------------------------------------------
Pr[INDR_CPA_direct(Compute, QueryBounder(A)).main() @ &m : Compute.bad] <=
(q * ell * (q * ell))%r * mu1 dBlock witness<:block> =>
`|Pr[IND(PRPi, PRPF_Adv(QueryBounder(A))).main() @ &m : res] -
  Pr[IND(PRFi, PRPF_Adv(QueryBounder(A))).main() @ &m : res]| <=
(q * ell * (q * ell - 1))%r / 2%r * mu1 dBlock witness<:block> =>
`|Pr[INDR_CPA(IV_Wrap(CBC(PseudoRP)), QueryBounder(A)).main() @ &m : res] -
  Pr[INDR_CPA(Random, QueryBounder(A)).main() @ &m : res]| <=
`|Pr[IND(PRP, PRPF_Adv(QueryBounder(A))).main() @ &m : res] -
  Pr[IND(PRPi, PRPF_Adv(QueryBounder(A))).main() @ &m : res]| +
`|Pr[IND(PRPi, PRPF_Adv(QueryBounder(A))).main() @ &m : res] -
  Pr[IND(PRFi, PRPF_Adv(QueryBounder(A))).main() @ &m : res]| +
Pr[INDR_CPA_direct(Compute, QueryBounder(A)).main() @ &m : Compute.bad] =>
`|Pr[INDR_CPA(IV_Wrap(CBC(PseudoRP)), QueryBounder(A)).main() @ &m : res] -
  Pr[INDR_CPA(Random, QueryBounder(A)).main() @ &m : res]| <=
`|Pr[IND(PRP, PRPF_Adv(QueryBounder(A))).main() @ &m : res] -
  Pr[IND(PRPi, PRPF_Adv(QueryBounder(A))).main() @ &m : res]| +
2%r * (q * ell * (q * ell))%r * mu1 dBlock witness<:block>
[161|check]>
```

**Last action:** `have ->: (q * ell) ^ 2 = q * ell * (q * ell) by rewrite expr2.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_Conclusion/r01/2026-06-11_1713_Conclusion/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_Conclusion/r01/2026-06-11_1713_Conclusion/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_Conclusion/r01/2026-06-11_1713_Conclusion/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_Conclusion/r01/2026-06-11_1713_Conclusion/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
