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
&2: {t1, t2, n, n0 : nonce, x, x0, x1, x2, x3, x4 : nonce * C.counter,
    r, r0, r1, r2, r3, r4 : poly_in, t, t0, t3, y, t4, y0 : poly_out,
    lt, lt0 : tag list}
neq: t1{2} <> t2{2}
hS1: (t1{2}, C.ofintd 0) \in SplitC2.I2.RO.m{2}
hS2: (t2{2}, C.ofintd 0) \notin SplitC2.I2.RO.m{2}
h3: (t1{2}, C.ofintd 0) \notin RO.m{2}
r4L: poly_in
h4: (t2{2}, C.ofintd 0) \notin RO.m{2}
t4L: poly_out
r1L: poly_in
------------------------------------------------------------------------
(t1{2}, C.ofintd 0) \notin RO.m{2}.[t2{2}, C.ofintd 0 <- r4L] =>
((t2{2}, C.ofintd 0) \notin RO.m{2}.[t1{2}, C.ofintd 0 <- r1L] =>
 (UF.forged{2} ||
  test_poly_in t1{2} Mem.lc{2}
    (oget RO.m{2}.[t1{2}, C.ofintd 0 <- r1L].[t1{2}, C.ofintd 0])
    (oget UFCMA.log{2}.[t1{2}])) =
 (UF.forged{2} ||
  test_poly_in t1{2} Mem.lc{2}
    (oget
       RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <- r1L].[t1{2}, 
       C.ofintd 0]) (oget UFCMA.log{2}.[t1{2}])) /\
 (UFCMA.bad2{2} ||
  (t4L \in
   map
     (fun (c : ciphertext) =>
        c.`4 -
        poly1305_eval
          (oget
             RO.m{2}.[t1{2}, C.ofintd 0 <- r1L].[t2{2}, C.ofintd 0 <- r4L].[t2{2}, 
             C.ofintd 0]) (topol c.`2 c.`3))
     (filter (fun (c : ciphertext) => c.`1 = t2{2}) Mem.lc{2}))) =
 (UFCMA.bad2{2} ||
  (t4L \in
   map
     (fun (c : ciphertext) =>
        c.`4 -
        poly1305_eval
          (oget RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t2{2}, C.ofintd 0])
          (topol c.`2 c.`3))
     (filter (fun (c : ciphertext) => c.`1 = t2{2}) Mem.lc{2}))) /\
 RO.m{2}.[t1{2}, C.ofintd 0 <- r1L].[t2{2}, C.ofintd 0 <- r4L] =
 RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <- r1L]) /\
((t2{2}, C.ofintd 0) \in RO.m{2}.[t1{2}, C.ofintd 0 <- r1L] =>
 (UF.forged{2} ||
  test_poly_in t1{2} Mem.lc{2}
    (oget RO.m{2}.[t1{2}, C.ofintd 0 <- r1L].[t1{2}, C.ofintd 0])
    (oget UFCMA.log{2}.[t1{2}])) =
 (UF.forged{2} ||
  test_poly_in t1{2} Mem.lc{2}
    (oget
       RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <- r1L].[t1{2}, 
       C.ofintd 0]) (oget UFCMA.log{2}.[t1{2}])) /\
 (UFCMA.bad2{2} ||
  (t4L \in
   map
     (fun (c : ciphertext) =>
        c.`4 -
        poly1305_eval
          (oget RO.m{2}.[t1{2}, C.ofintd 0 <- r1L].[t2{2}, C.ofintd 0])
          (topol c.`2 c.`3))
     (filter (fun (c : ciphertext) => c.`1 = t2{2}) Mem.lc{2}))) =
 (UFCMA.bad2{2} ||
  (t4L \in
   map
     (fun (c : ciphertext) =>
        c.`4 -
        poly1305_eval
          (oget RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t2{2}, C.ofintd 0])
          (topol c.`2 c.`3))
     (filter (fun (c : ciphertext) => c.`1 = t2{2}) Mem.lc{2}))) /\
 RO.m{2}.[t1{2}, C.ofintd 0 <- r1L] =
 RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <- r1L])
[430|check]>
```

**Last action:** `move => h4 t4L _ r1L _; split; last by smt(mem_set).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
