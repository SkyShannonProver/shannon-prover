## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
nth0: int
h0nth0: 0 <= nth0
hnth0q: nth0 < qdec
------------------------------------------------------------------------
&1 (left ) : {p : plaintext, c : ciphertext}
&2 (right) : {p : plaintext, c : ciphertext}

pre =
  (c{2} = witness<:ciphertext> /\
   c{1} = witness<:ciphertext> /\
   p{1} = p{2} /\
   (BNR.lenc{1} = BNR.lenc{2} /\
    BNR.ndec{1} = BNR.ndec{2} /\
    Mem.log{1} = Mem.log{2} /\
    Mem.lc{1} = Mem.lc{2} /\
    UFCMA.log{1} = UFCMA.log{2} /\
    UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
    UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\
    RO.m{1} = RO.m{2} /\
    SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
    SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
   UFCMA_li.i{2} = nth0 /\
   (UFCMA_li.cbadi{2} = if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\
   (nth0 < size UFCMA_l.lbad1{2} =>
    (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
    (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2})) /\
  check_plaintext BNR.lenc{1} p{1}

c <@ CPA_CCA_Orcls(UFCMA_l.O).enc(p)  (1)  c <@ CPA_CCA_Orcls(UFCMA_li.O).enc(p)
BNR.lenc <- p.`1 :: BNR.lenc          (2)  BNR.lenc <- p.`1 :: BNR.lenc         

post =
  c{1} = c{2} /\
  (BNR.lenc{1} = BNR.lenc{2} /\
   BNR.ndec{1} = BNR.ndec{2} /\
   Mem.log{1} = Mem.log{2} /\
   Mem.lc{1} = Mem.lc{2} /\
   UFCMA.log{1} = UFCMA.log{2} /\
   UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
   UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\
   RO.m{1} = RO.m{2} /\
   SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
   SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
  UFCMA_li.i{2} = nth0 /\
  (UFCMA_li.cbadi{2} = if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\
  (nth0 < size UFCMA_l.lbad1{2} =>
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2})
[426|check]>
```

**Last action:** `sp; if => //.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
