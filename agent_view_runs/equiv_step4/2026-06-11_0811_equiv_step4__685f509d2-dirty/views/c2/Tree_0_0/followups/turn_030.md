## 🎯 Current Goal
```
Current goal (remaining: 6)

Type variables: <none>

eqRO: equiv[ RO.get  ~ RO.get :
              arg{1} = arg{2} /\ RO.m{1} = RO.m{2} ==>
              res{1} = res{2} /\ RO.m{1} = RO.m{2}]
eqSB2: equiv[ UFCMA(RO).set_bad2  ~ UFCMA(RO).set_bad2 :
               arg{1} = arg{2} /\
               UFCMA.bad2{1} = UFCMA.bad2{2} /\
               UFCMA.cbad2{1} = UFCMA.cbad2{2} ==>
               res{1} = res{2} /\
               UFCMA.bad2{1} = UFCMA.bad2{2} /\
               UFCMA.cbad2{1} = UFCMA.cbad2{2}]
eqf: equiv[ Orcl.f  ~ Orcl.f :
             arg{1} = arg{2} /\
             (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1},
              RO.m{1}, Mem.lc{1}, SplitC2.I2.RO.m{1}) =
             (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2},
              RO.m{2}, Mem.lc{2}, SplitC2.I2.RO.m{2}) ==>
             (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1},
              RO.m{1}, Mem.lc{1}, SplitC2.I2.RO.m{1}) =
             (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2},
              RO.m{2}, Mem.lc{2}, SplitC2.I2.RO.m{2})]
Hsw: equiv[ Iter(Orcl).iter_12  ~ Iter(Orcl).iter_21 :
             (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1},
              RO.m{1}, Mem.lc{1}, SplitC2.I2.RO.m{1}) =
             (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2},
              RO.m{2}, Mem.lc{2}, SplitC2.I2.RO.m{2}) /\
             t1{1} = t1{2} /\ t2{1} = t2{2} ==>
             (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1},
              RO.m{1}, Mem.lc{1}, SplitC2.I2.RO.m{1}) =
             (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2},
              RO.m{2}, Mem.lc{2}, SplitC2.I2.RO.m{2})]
------------------------------------------------------------------------
pre =
  arg{1} = arg{2} /\
  UFCMA.log{1} = UFCMA.log{2} /\
  UFCMA.bad1{1} = UFCMA.bad1{2} /\
  UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
  UFCMA.bad2{1} = UFCMA.bad2{2} /\
  UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
  Mem.log{1} = Mem.log{2} /\
  Mem.lc{1} = Mem.lc{2} /\
  RO.m{1} = RO.m{2} /\
  SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
  BNR.lenc{1} = BNR.lenc{2} /\ BNR.ndec{1} = BNR.ndec{2}

    BNR(CPA_CCA_Orcls(UFCMA(RO).O)).enc ~ BNR(CPA_CCA_Orcls(UFCMA(RO).O)).enc 

post =
  res{1} = res{2} /\
  UFCMA.log{1} = UFCMA.log{2} /\
  UFCMA.bad1{1} = UFCMA.bad1{2} /\
  UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
  UFCMA.bad2{1} = UFCMA.bad2{2} /\
  UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
  Mem.log{1} = Mem.log{2} /\
  Mem.lc{1} = Mem.lc{2} /\
  RO.m{1} = RO.m{2} /\
  SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
  BNR.lenc{1} = BNR.lenc{2} /\ BNR.ndec{1} = BNR.ndec{2}
[498|check]>
```

**Last action:** `proc; inline *; wp; call (_: ={UFCMA.log, UFCMA.bad1, UFCMA.cbad1, UFCMA.bad2, …` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
