## 🎯 Current Goal
```
Current goal (remaining: 4)

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
eqSet: equiv[ ROout.set  ~ ROout.set :
               arg{1} = arg{2} /\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} ==>
               SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2}]
------------------------------------------------------------------------
&1 (left ) : {b, forged : bool, i : int, n : nonce, ns : nonce list,
             r : poly_in, t : poly_out}
&2 (right) : {b : bool, n : nonce, ns, ns1, ns2, l : nonce list, r : poly_in,
             t : poly_out}

pre =
  forged{1} = UF.forged{2} /\
  (UFCMA.bad2{1} = UFCMA.bad2{2} /\
   UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
   UFCMA.log{1} = UFCMA.log{2} /\
   Mem.lc{1} = Mem.lc{2} /\
   RO.m{1} = RO.m{2} /\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2}) /\
  ns{1} = ns{2}

i <- 0                     (1)  l <- ns                  

post =
  ((0 <= i{1} /\
    l{2} = drop i{1} ns{1} /\
    forged{1} = UF.forged{2} /\
    UFCMA.bad2{1} = UFCMA.bad2{2} /\
    UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
    UFCMA.log{1} = UFCMA.log{2} /\
    Mem.lc{1} = Mem.lc{2} /\
    RO.m{1} = RO.m{2} /\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2}) /\
   (i{1} < size ns{1} <=> l{2} <> [])) /\
  forall (bad2_L : bool) (cbad2_L : int) (m_L : (nonce * C.counter,
    poly_in) fmap) (m_L0 : (nonce * C.counter, poly_out) fmap)
    (forged_L : bool) (i_L : int) (forged_R bad2_R : bool) (cbad2_R : int)
    (m_R : (nonce * C.counter, poly_in) fmap) (m_R0 : (nonce * C.counter,
    poly_out) fmap) (l_R : nonce list),
    ! i_L < size ns{1} =>
    l_R = [] =>
    0 <= i_L /\
    l_R = drop i_L ns{1} /\
    forged_L = forged_R /\
    bad2_L = bad2_R /\
    cbad2_L = cbad2_R /\
    UFCMA.log{1} = UFCMA.log{2} /\
    Mem.lc{1} = Mem.lc{2} /\ m_L = m_R /\ m_L0 = m_R0 =>
    bad2_L = bad2_R /\ forged_L = forged_R
[515|check]>
```

**Last action:** `by wp; call eqSet; call eqSB2; call eqRO; auto; smt(drop_nth drop_drop size_dro…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
