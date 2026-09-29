## 🎯 Current Goal
```
Current goal (remaining: 3)

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
&1: {b : bool, n : nonce, ns, ns1, ns2, l1, l2, l, l0 : nonce list,
    x : nonce * C.counter, r : poly_in, t, y : poly_out}
&2: {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list, r : poly_in,
    t : poly_out}
hn2: n{2} = nth witness<:nonce> ns2{2} i{2}
hn1: n{1} = head witness<:nonce> l0{1}
hf: UF.forged{1} = UF.forged{2}
hb: UFCMA.bad2{1} = UFCMA.bad2{2}
hcb: UFCMA.cbad2{1} = UFCMA.cbad2{2}
hlog: UFCMA.log{1} = UFCMA.log{2}
hlc: Mem.lc{1} = Mem.lc{2}
hro: RO.m{1} = RO.m{2}
hl0: l0{1} = drop i{2} ns2{2}
hi: 0 <= i{2}
hu: uniq l0{1}
hnotin: forall (n0 : nonce),
          n0 \in l0{1} => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{1}
hne: l0{1} <> []
hlt: i{2} < size ns2{2}
hd: drop i{2} ns2{2} = n{2} :: drop (i{2} + 1) ns2{2}
hn12: n{1} = n{2}
------------------------------------------------------------------------
((n{1}, C.ofintd 0) = (n{2}, C.ofintd 0) /\ RO.m{1} = RO.m{2}) &&
forall (result_L result_R : poly_in) (m_L m_R : (nonce * C.counter,
  poly_in) fmap),
  result_L = result_R /\ m_L = m_R =>
  (map
     (fun (c : ciphertext) => c.`4 - poly1305_eval result_L (topol c.`2 c.`3))
     (filter (fun (c : ciphertext) => c.`1 = n{1}) Mem.lc{1}) =
   map
     (fun (c : ciphertext) => c.`4 - poly1305_eval result_R (topol c.`2 c.`3))
     (filter (fun (c : ciphertext) => c.`1 = n{2}) Mem.lc{2}) /\
   UFCMA.bad2{1} = UFCMA.bad2{2} /\ UFCMA.cbad2{1} = UFCMA.cbad2{2}) &&
  forall (result_L0 result_R0 : poly_out) (bad2_L : bool) (cbad2_L : int)
    (bad2_R : bool) (cbad2_R : int),
    result_L0 = result_R0 /\ bad2_L = bad2_R /\ cbad2_L = cbad2_R =>
    let i_R = i{2} + 1 in
    let l0_L = drop 1 l0{1} in
    (UF.forged{1} = UF.forged{2} /\
     bad2_L = bad2_R /\
     cbad2_L = cbad2_R /\
     UFCMA.log{1} = UFCMA.log{2} /\
     Mem.lc{1} = Mem.lc{2} /\
     m_L = m_R /\
     l0_L = drop i_R ns2{2} /\
     0 <= i_R /\
     uniq l0_L /\
     forall (n0 : nonce),
       n0 \in l0_L =>
       (n0, C.ofintd 0) \notin
       SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness<:poly_out>]) /\
    (l0_L <> [] <=> i_R < size ns2{2})
[558|check]>
```

**Last action:** `smt(drop_drop mem_set cons_uniq mem_drop size_drop size_eq0 size_ge0 in_cons ge…` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] cannot prove goal (strict)`

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
