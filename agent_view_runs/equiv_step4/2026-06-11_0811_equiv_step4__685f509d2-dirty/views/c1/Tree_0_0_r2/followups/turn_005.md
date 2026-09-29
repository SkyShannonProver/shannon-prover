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
------------------------------------------------------------------------
forall &1 &2,
  (((((UF.forged{1} = UF.forged{2} /\
       UFCMA.bad2{1} = UFCMA.bad2{2} /\
       UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
       UFCMA.log{1} = UFCMA.log{2} /\
       RO.m{1} = RO.m{2} /\
       Mem.lc{1} = Mem.lc{2} /\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2}) /\
      t1{1} = t1{2} /\ t2{1} = t2{2}) /\
     t1{1} <> t2{1}) /\
    ((t1{1}, C.ofintd 0) \in SplitC2.I2.RO.m{1})) /\
   ((t2{1}, C.ofintd 0) \notin SplitC2.I2.RO.m{1})) /\
  ((t1{1}, C.ofintd 0) \notin RO.m{1}) =>
  let x0_R = (t2{2}, C.ofintd 0) in
  let x_L = (t1{1}, C.ofintd 0) in
  (forall (r2R : poly_in), r2R \in dpoly_in => r2R = r2R) &&
  forall (r4L : poly_in),
    r4L \in dpoly_in =>
    r4L = r4L &&
    if x0_R \notin RO.m{2} then
      let m_R = RO.m{2}.[x0_R <- r4L] in
      (forall (t3R : poly_out), t3R \in dpoly_out => t3R = t3R) &&
      forall (t4L : poly_out),
        t4L \in dpoly_out =>
        t4L = t4L &&
        let bad2_R =
          UFCMA.bad2{2} ||
          (t4L \in
           map
             (fun (c : ciphertext) =>
                c.`4 - poly1305_eval (oget m_R.[x0_R]) (topol c.`2 c.`3))
             (filter (fun (c : ciphertext) => c.`1 = t2{2}) Mem.lc{2})) in
        let cbad2_R = UFCMA.cbad2{2} + 1 in
        let m_R0 =
          SplitC2.I2.RO.m{2}.[t2{2}, C.ofintd 0 <- witness<:poly_out>] in
        let x2_R = (t1{2}, C.ofintd 0) in
        (forall (r3R : poly_in), r3R \in dpoly_in => r3R = r3R) &&
        forall (r1L : poly_in),
          r1L \in dpoly_in =>
          r1L = r1L &&
          if x2_R \notin m_R then
            let m_R1 = m_R.[x2_R <- r1L] in
            let forged_R =
              UF.forged{2} ||
              test_poly_in t1{2} Mem.lc{2} (oget m_R1.[x2_R])
                (oget UFCMA.log{2}.[t1{2}]) in
            if x_L \notin RO.m{1} then
              let m_L = RO.m{1}.[x_L <- r1L] in
              let forged_L =
                UF.forged{1} ||
                test_poly_in t1{1} Mem.lc{1} (oget m_L.[x_L])
                  (oget UFCMA.log{1}.[t1{1}]) in
              let x3_L = (t2{1}, C.ofintd 0) in
              if x3_L \notin m_L then
                let m_L0 = m_L.[x3_L <- r4L] in
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget m_L0.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                m_L0 = m_R1 /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R0
              else
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget m_L.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                m_L = m_R1 /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R0
            else
              let forged_L =
                UF.forged{1} ||
                test_poly_in t1{1} Mem.lc{1} (oget RO.m{1}.[x_L])
                  (oget UFCMA.log{1}.[t1{1}]) in
              let x3_L = (t2{1}, C.ofintd 0) in
              if x3_L \notin RO.m{1} then
                let m_L = RO.m{1}.[x3_L <- r4L] in
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget m_L.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                m_L = m_R1 /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R0
              else
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget RO.m{1}.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                RO.m{1} = m_R1 /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R0
          else
            let forged_R =
              UF.forged{2} ||
              test_poly_in t1{2} Mem.lc{2} (oget m_R.[x2_R])
                (oget UFCMA.log{2}.[t1{2}]) in
            if x_L \notin RO.m{1} then
              let m_L = RO.m{1}.[x_L <- r1L] in
              let forged_L =
                UF.forged{1} ||
                test_poly_in t1{1} Mem.lc{1} (oget m_L.[x_L])
                  (oget UFCMA.log{1}.[t1{1}]) in
              let x3_L = (t2{1}, C.ofintd 0) in
              if x3_L \notin m_L then
                let m_L0 = m_L.[x3_L <- r4L] in
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget m_L0.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                m_L0 = m_R /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R0
              else
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget m_L.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                m_L = m_R /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R0
            else
              let forged_L =
                UF.forged{1} ||
                test_poly_in t1{1} Mem.lc{1} (oget RO.m{1}.[x_L])
                  (oget UFCMA.log{1}.[t1{1}]) in
              let x3_L = (t2{1}, C.ofintd 0) in
              if x3_L \notin RO.m{1} then
                let m_L = RO.m{1}.[x3_L <- r4L] in
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget m_L.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                m_L = m_R /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R0
              else
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget RO.m{1}.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                RO.m{1} = m_R /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R0
    else
      (forall (t3R : poly_out), t3R \in dpoly_out => t3R = t3R) &&
      forall (t4L : poly_out),
        t4L \in dpoly_out =>
        t4L = t4L &&
        let bad2_R =
          UFCMA.bad2{2} ||
          (t4L \in
           map
             (fun (c : ciphertext) =>
                c.`4 - poly1305_eval (oget RO.m{2}.[x0_R]) (topol c.`2 c.`3))
             (filter (fun (c : ciphertext) => c.`1 = t2{2}) Mem.lc{2})) in
        let cbad2_R = UFCMA.cbad2{2} + 1 in
        let m_R =
          SplitC2.I2.RO.m{2}.[t2{2}, C.ofintd 0 <- witness<:poly_out>] in
        let x2_R = (t1{2}, C.ofintd 0) in
        (forall (r3R : poly_in), r3R \in dpoly_in => r3R = r3R) &&
        forall (r1L : poly_in),
          r1L \in dpoly_in =>
          r1L = r1L &&
          if x2_R \notin RO.m{2} then
            let m_R0 = RO.m{2}.[x2_R <- r1L] in
            let forged_R =
              UF.forged{2} ||
              test_poly_in t1{2} Mem.lc{2} (oget m_R0.[x2_R])
                (oget UFCMA.log{2}.[t1{2}]) in
            if x_L \notin RO.m{1} then
              let m_L = RO.m{1}.[x_L <- r1L] in
              let forged_L =
                UF.forged{1} ||
                test_poly_in t1{1} Mem.lc{1} (oget m_L.[x_L])
                  (oget UFCMA.log{1}.[t1{1}]) in
              let x3_L = (t2{1}, C.ofintd 0) in
              if x3_L \notin m_L then
                let m_L0 = m_L.[x3_L <- r4L] in
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget m_L0.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                m_L0 = m_R0 /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R
              else
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget m_L.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                m_L = m_R0 /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R
            else
              let forged_L =
                UF.forged{1} ||
                test_poly_in t1{1} Mem.lc{1} (oget RO.m{1}.[x_L])
                  (oget UFCMA.log{1}.[t1{1}]) in
              let x3_L = (t2{1}, C.ofintd 0) in
              if x3_L \notin RO.m{1} then
                let m_L = RO.m{1}.[x3_L <- r4L] in
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget m_L.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                m_L = m_R0 /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R
              else
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget RO.m{1}.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                RO.m{1} = m_R0 /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R
          else
            let forged_R =
              UF.forged{2} ||
              test_poly_in t1{2} Mem.lc{2} (oget RO.m{2}.[x2_R])
                (oget UFCMA.log{2}.[t1{2}]) in
            if x_L \notin RO.m{1} then
              let m_L = RO.m{1}.[x_L <- r1L] in
              let forged_L =
                UF.forged{1} ||
                test_poly_in t1{1} Mem.lc{1} (oget m_L.[x_L])
                  (oget UFCMA.log{1}.[t1{1}]) in
              let x3_L = (t2{1}, C.ofintd 0) in
              if x3_L \notin m_L then
                let m_L0 = m_L.[x3_L <- r4L] in
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget m_L0.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                m_L0 = RO.m{2} /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R
              else
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget m_L.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                m_L = RO.m{2} /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R
            else
              let forged_L =
                UF.forged{1} ||
                test_poly_in t1{1} Mem.lc{1} (oget RO.m{1}.[x_L])
                  (oget UFCMA.log{1}.[t1{1}]) in
              let x3_L = (t2{1}, C.ofintd 0) in
              if x3_L \notin RO.m{1} then
                let m_L = RO.m{1}.[x3_L <- r4L] in
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget m_L.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                m_L = RO.m{2} /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R
              else
                forged_L = forged_R /\
                (UFCMA.bad2{1} ||
                 (t4L \in
                  map
                    (fun (c : ciphertext) =>
                       c.`4 -
                       poly1305_eval (oget RO.m{1}.[x3_L]) (topol c.`2 c.`3))
                    (filter (fun (c : ciphertext) => c.`1 = t2{1}) Mem.lc{1}))) =
                bad2_R /\
                UFCMA.cbad2{1} + 1 = cbad2_R /\
                UFCMA.log{1} = UFCMA.log{2} /\
                RO.m{1} = RO.m{2} /\
                Mem.lc{1} = Mem.lc{2} /\
                SplitC2.I2.RO.m{1}.[t2{1}, C.ofintd 0 <- witness<:poly_out>] =
                m_R
[427|check]>
```

**Last action:** `auto.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
