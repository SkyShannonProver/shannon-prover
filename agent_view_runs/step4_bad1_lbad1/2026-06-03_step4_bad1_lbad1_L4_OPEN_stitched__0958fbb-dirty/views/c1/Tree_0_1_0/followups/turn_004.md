## 🎯 Current Goal
```
Current goal (remaining: 5)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {i : int, c2 : byte list, n, n0 : nonce,
             x, x0, x1 : nonce * C.counter, c1 : bytes, r : poly_in,
             t, t0, y : poly_out, z : block, a : associated_data,
             p1, p2 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext, lt : tag list} [programs are in sync]
&2 (right) : {i : int, c2 : byte list, n, n0 : nonce,
             x, x0, x1 : nonce * C.counter, c1 : bytes, r : poly_in,
             t, t0, y : poly_out, z : block, a : associated_data,
             p1, p2 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext, lt : tag list}

pre =
  (exists (cbad1_R : int) (lbad1_R : (tag * tag) list),
     UFCMA_l.lbad1{2} = lbad1_R ++ map (fun (t' : tag) => (t0{2}, t')) lt{2} /\
     UFCMA.cbad1{2} = cbad1_R + 1 /\
     t{2} = t0{2} /\
     x{2} = (n{2}, C.ofintd 0) /\
     x1{2} = x{2} /\
     exists (cbad1_L : int) (bad1_L : bool),
       UFCMA.bad1{1} = (bad1_L || (t0{1} \in lt{1})) /\
       UFCMA.cbad1{1} = cbad1_L + 1 /\
       t{1} = t0{1} /\
       x{1} = (n{1}, C.ofintd 0) /\
       x1{1} = x{1} /\
       ((n{1} = n{2} /\
         a{1} = a{2} /\
         c1{1} = c1{2} /\
         lt{1} = lt{2} /\
         t0{1} = t0{2} /\
         p0{1} = p0{2} /\
         p{1} = p{2} /\
         Mem.log{1} = Mem.log{2} /\
         Mem.lc{1} = Mem.lc{2} /\
         BNR.lenc{1} = BNR.lenc{2} /\
         BNR.ndec{1} = BNR.ndec{2} /\
         UFCMA.log{1} = UFCMA.log{2} /\
         cbad1_L = cbad1_R /\
         RO.m{1} = RO.m{2} /\
         SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
         SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
        (uniq BNR.lenc{2} /\
         cbad1_R <= qenc /\
         size BNR.lenc{2} <= qenc /\
         size lbad1_R <=
         size (make_lbad1 UFCMA.log{2} Mem.lc{2} BNR.lenc{2}) <= qdec /\
         size Mem.lc{2} <= BNR.ndec{2} <= qdec /\
         uniq BNR.lenc{2} /\
         (forall (n1 : nonce),
            n1 \in BNR.lenc{2} =>
            let (a0, c3, t1) = oget UFCMA.log{2}.[n1] in
            (n1, a0, c3, t1) \in Mem.log{2}) /\
         (forall (n1 : nonce), (n1 \in BNR.lenc{2}) = (n1 \in UFCMA.log{2})) /\
         forall (t1 t' : tag),
           (t1, t') \in lbad1_R =>
           exists (n1 : nonce),
             (n1 \in BNR.lenc{2}) /\
             (oget UFCMA.log{2}.[n1]).`3 = t1 /\
             exists (a0 : associated_data) (c3 : message),
               (n1, a0, c3, t') \in Mem.lc{2}) /\
        (bad1_L <=>
         exists (tt : tag * tag), (tt \in lbad1_R) /\ tt.`1 = tt.`2) /\
        check_plaintext BNR.lenc{1} p{1} /\
        n{1} = p{1}.`1 /\
        lt{2} =
        map (fun (c3 : ciphertext) => c3.`4)
          (filter (fun (c3 : ciphertext) => c3.`1 = n{2}) Mem.lc{2})) /\
       cbad1_L < qenc /\ size lt{1} <= qdec) /\
  r{1} = r{2}


post =
  (x1{2} \notin RO.m{2} =>
   (x1{1} \notin RO.m{1} =>
    (n{1} = n{2} /\ a{1} = a{2} /\ c1{1} = c1{2} /\ t{1} = t{2}) /\
    (Mem.log{1}.[n{1}, a{1}, c1{1}, t{1} <- p0{1}] =
     Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}] /\
     Mem.lc{1} = Mem.lc{2} /\
     (p{1}.`1 = p{2}.`1 /\ BNR.lenc{1} = BNR.lenc{2}) /\
     BNR.ndec{1} = BNR.ndec{2} /\
     UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] =
     UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] /\
     UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
     RO.m{1}.[x1{1} <- r{2}] = RO.m{2}.[x1{2} <- r{2}] /\
     SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness] =
     SplitC2.I2.RO.m{2}.[n{2}, C.ofintd 0 <- witness] /\
     SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
    ((! (p{2}.`1 \in BNR.lenc{2}) /\ uniq BNR.lenc{2}) /\
     UFCMA.cbad1{2} <= qenc /\
     1 + size BNR.lenc{2} <= qenc /\
     (size UFCMA_l.lbad1{2} <=
      size
        (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2}
           (p{2}.`1 :: BNR.lenc{2})) /\
      (size UFCMA_l.lbad1{2} <=
       size
         (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2}
            (p{2}.`1 :: BNR.lenc{2})) =>
       size
         (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2}
            (p{2}.`1 :: BNR.lenc{2})) <=
       qdec)) /\
     (size Mem.lc{2} <= BNR.ndec{2} /\
      (size Mem.lc{2} <= BNR.ndec{2} => BNR.ndec{2} <= qdec)) /\
     (! (p{2}.`1 \in BNR.lenc{2}) /\ uniq BNR.lenc{2}) /\
     (forall (n1 : nonce),
        n1 = p{2}.`1 \/ (n1 \in BNR.lenc{2}) =>
        forall (x10 : associated_data) (x2 : message) (x3 : tag),
          oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1] =
          (x10, x2, x3) =>
          (n1, x10, x2, x3) \in Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}]) /\
     (forall (n1 : nonce),
        (n1 = p{2}.`1 \/ (n1 \in BNR.lenc{2})) =
        (n1 \in UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})])) /\
     forall (t1 t' : tag),
       (t1, t') \in UFCMA_l.lbad1{2} =>
       exists (n1 : nonce),
         (n1 = p{2}.`1 \/ (n1 \in BNR.lenc{2})) /\
         (oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1]).`3 = t1 /\
         exists (a0 : associated_data) (c3 : message),
           (n1, a0, c3, t') \in Mem.lc{2}) /\
    (UFCMA.bad1{1} =>
     exists (tt : tag * tag), (tt \in UFCMA_l.lbad1{2}) /\ tt.`1 = tt.`2) /\
    forall (tt : tag * tag),
      tt \in UFCMA_l.lbad1{2} => tt.`1 = tt.`2 => UFCMA.bad1{1}) /\
   (x1{1} \in RO.m{1} =>
    (n{1} = n{2} /\ a{1} = a{2} /\ c1{1} = c1{2} /\ t{1} = t{2}) /\
    (Mem.log{1}.[n{1}, a{1}, c1{1}, t{1} <- p0{1}] =
     Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}] /\
     Mem.lc{1} = Mem.lc{2} /\
     (p{1}.`1 = p{2}.`1 /\ BNR.lenc{1} = BNR.lenc{2}) /\
     BNR.ndec{1} = BNR.ndec{2} /\
     UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] =
     UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] /\
     UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
     RO.m{1} = RO.m{2}.[x1{2} <- r{2}] /\
     SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness] =
     SplitC2.I2.RO.m{2}.[n{2}, C.ofintd 0 <- witness] /\
     SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
    ((! (p{2}.`1 \in BNR.lenc{2}) /\ uniq BNR.lenc{2}) /\
     UFCMA.cbad1{2} <= qenc /\
     1 + size BNR.lenc{2} <= qenc /\
     (size UFCMA_l.lbad1{2} <=
      size
        (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2}
           (p{2}.`1 :: BNR.lenc{2})) /\
      (size UFCMA_l.lbad1{2} <=
       size
         (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2}
            (p{2}.`1 :: BNR.lenc{2})) =>
       size
         (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2}
            (p{2}.`1 :: BNR.lenc{2})) <=
       qdec)) /\
     (size Mem.lc{2} <= BNR.ndec{2} /\
      (size Mem.lc{2} <= BNR.ndec{2} => BNR.ndec{2} <= qdec)) /\
     (! (p{2}.`1 \in BNR.lenc{2}) /\ uniq BNR.lenc{2}) /\
     (forall (n1 : nonce),
        n1 = p{2}.`1 \/ (n1 \in BNR.lenc{2}) =>
        forall (x10 : associated_data) (x2 : message) (x3 : tag),
          oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1] =
          (x10, x2, x3) =>
          (n1, x10, x2, x3) \in Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}]) /\
     (forall (n1 : nonce),
        (n1 = p{2}.`1 \/ (n1 \in BNR.lenc{2})) =
        (n1 \in UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})])) /\
     forall (t1 t' : tag),
       (t1, t') \in UFCMA_l.lbad1{2} =>
       exists (n1 : nonce),
         (n1 = p{2}.`1 \/ (n1 \in BNR.lenc{2})) /\
         (oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1]).`3 = t1 /\
         exists (a0 : associated_data) (c3 : message),
           (n1, a0, c3, t') \in Mem.lc{2}) /\
    (UFCMA.bad1{1} =>
     exists (tt : tag * tag), (tt \in UFCMA_l.lbad1{2}) /\ tt.`1 = tt.`2) /\
    forall (tt : tag * tag),
      tt \in UFCMA_l.lbad1{2} => tt.`1 = tt.`2 => UFCMA.bad1{1})) /\
  (x1{2} \in RO.m{2} =>
   (x1{1} \notin RO.m{1} =>
    (n{1} = n{2} /\ a{1} = a{2} /\ c1{1} = c1{2} /\ t{1} = t{2}) /\
    (Mem.log{1}.[n{1}, a{1}, c1{1}, t{1} <- p0{1}] =
     Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}] /\
     Mem.lc{1} = Mem.lc{2} /\
     (p{1}.`1 = p{2}.`1 /\ BNR.lenc{1} = BNR.lenc{2}) /\
     BNR.ndec{1} = BNR.ndec{2} /\
     UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] =
     UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] /\
     UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
     RO.m{1}.[x1{1} <- r{2}] = RO.m{2} /\
     SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness] =
     SplitC2.I2.RO.m{2}.[n{2}, C.ofintd 0 <- witness] /\
     SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
    ((! (p{2}.`1 \in BNR.lenc{2}) /\ uniq BNR.lenc{2}) /\
     UFCMA.cbad1{2} <= qenc /\
     1 + size BNR.lenc{2} <= qenc /\
     (size UFCMA_l.lbad1{2} <=
      size
        (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2}
           (p{2}.`1 :: BNR.lenc{2})) /\
      (size UFCMA_l.lbad1{2} <=
       size
         (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2}
            (p{2}.`1 :: BNR.lenc{2})) =>
       size
         (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2}
            (p{2}.`1 :: BNR.lenc{2})) <=
       qdec)) /\
     (size Mem.lc{2} <= BNR.ndec{2} /\
      (size Mem.lc{2} <= BNR.ndec{2} => BNR.ndec{2} <= qdec)) /\
     (! (p{2}.`1 \in BNR.lenc{2}) /\ uniq BNR.lenc{2}) /\
     (forall (n1 : nonce),
        n1 = p{2}.`1 \/ (n1 \in BNR.lenc{2}) =>
        forall (x10 : associated_data) (x2 : message) (x3 : tag),
          oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1] =
          (x10, x2, x3) =>
          (n1, x10, x2, x3) \in Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}]) /\
     (forall (n1 : nonce),
        (n1 = p{2}.`1 \/ (n1 \in BNR.lenc{2})) =
        (n1 \in UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})])) /\
     forall (t1 t' : tag),
       (t1, t') \in UFCMA_l.lbad1{2} =>
       exists (n1 : nonce),
         (n1 = p{2}.`1 \/ (n1 \in BNR.lenc{2})) /\
         (oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1]).`3 = t1 /\
         exists (a0 : associated_data) (c3 : message),
           (n1, a0, c3, t') \in Mem.lc{2}) /\
    (UFCMA.bad1{1} =>
     exists (tt : tag * tag), (tt \in UFCMA_l.lbad1{2}) /\ tt.`1 = tt.`2) /\
    forall (tt : tag * tag),
      tt \in UFCMA_l.lbad1{2} => tt.`1 = tt.`2 => UFCMA.bad1{1}) /\
   (x1{1} \in RO.m{1} =>
    (n{1} = n{2} /\ a{1} = a{2} /\ c1{1} = c1{2} /\ t{1} = t{2}) /\
    (Mem.log{1}.[n{1}, a{1}, c1{1}, t{1} <- p0{1}] =
     Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}] /\
     Mem.lc{1} = Mem.lc{2} /\
     (p{1}.`1 = p{2}.`1 /\ BNR.lenc{1} = BNR.lenc{2}) /\
     BNR.ndec{1} = BNR.ndec{2} /\
     UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] =
     UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] /\
     UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
     RO.m{1} = RO.m{2} /\
     SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness] =
     SplitC2.I2.RO.m{2}.[n{2}, C.ofintd 0 <- witness] /\
     SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
    ((! (p{2}.`1 \in BNR.lenc{2}) /\ uniq BNR.lenc{2}) /\
     UFCMA.cbad1{2} <= qenc /\
     1 + size BNR.lenc{2} <= qenc /\
     (size UFCMA_l.lbad1{2} <=
      size
        (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2}
           (p{2}.`1 :: BNR.lenc{2})) /\
      (size UFCMA_l.lbad1{2} <=
       size
         (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2}
            (p{2}.`1 :: BNR.lenc{2})) =>
       size
         (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2}
            (p{2}.`1 :: BNR.lenc{2})) <=
       qdec)) /\
     (size Mem.lc{2} <= BNR.ndec{2} /\
      (size Mem.lc{2} <= BNR.ndec{2} => BNR.ndec{2} <= qdec)) /\
     (! (p{2}.`1 \in BNR.lenc{2}) /\ uniq BNR.lenc{2}) /\
     (forall (n1 : nonce),
        n1 = p{2}.`1 \/ (n1 \in BNR.lenc{2}) =>
        forall (x10 : associated_data) (x2 : message) (x3 : tag),
          oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1] =
          (x10, x2, x3) =>
          (n1, x10, x2, x3) \in Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}]) /\
     (forall (n1 : nonce),
        (n1 = p{2}.`1 \/ (n1 \in BNR.lenc{2})) =
        (n1 \in UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})])) /\
     forall (t1 t' : tag),
       (t1, t') \in UFCMA_l.lbad1{2} =>
       exists (n1 : nonce),
         (n1 = p{2}.`1 \/ (n1 \in BNR.lenc{2})) /\
         (oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1]).`3 = t1 /\
         exists (a0 : associated_data) (c3 : message),
           (n1, a0, c3, t') \in Mem.lc{2}) /\
    (UFCMA.bad1{1} =>
     exists (tt : tag * tag), (tt \in UFCMA_l.lbad1{2}) /\ tt.`1 = tt.`2) /\
    forall (tt : tag * tag),
      tt \in UFCMA_l.lbad1{2} => tt.`1 = tt.`2 => UFCMA.bad1{1}))
[422|check]>
```

## Status
remaining **5** · phase `relational_program` / `verification_residue`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The visible frontier contains call sites or named equiv handles may apply.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are at an abstract-adversary `call (_: <inv>)` and want the mechanical glob frame of the invariant before adding yo…
  submit `{"intent": "inspect_context", "payload": {"topic": "call_invariant_skeleton"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- A tactic has multiple EasyCrypt argument forms.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The frontier may need indexed `sp i j` before branch or call tactics.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "sp"}}`
- Mid-proof pRHL suffix surgery may need indexed `wp`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "wp"}}`
- Statement order may need a small `swap` before `sp`, `wp`, or `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "swap"}}`
- A guarded branch may need `rcondt` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondt"}}`
- A guarded branch may need `rcondf` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondf"}}`
- A suffix proof may need `conseq` to weaken to a smaller relation before `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "conseq"}}`
- One side may have an extra sample or need an explicit sample coupling.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rnd"}}`
- A known statement-order mismatch may need an eager/lazy transformation.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "eager"}}`
- LHS/RHS statement order may need swap/alignment context.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`

_(full untruncated view: `latest_workspace_view.json`)_

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `inspect_context`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

```json
{"turn":4,"handled_intent":{"intent":"inspect_context","payload":{"topic":"goal_info"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"inspect goal info","outcome":"The manager returned read-only context for the current goal.","timing":"1.3 s","content":{"title":"Parsed Goal Information","goal_info":{"goal_type":"pRHL","num_remaining":5,"num_remaining_determined":true,"pre":"pre = (exists (cbad1_R : int) (lbad1_R : (tag * tag) list), UFCMA_l.lbad1{2} = lbad1_R ++ map (fun (t' : tag) => (t0{2}, t')) lt{2} /\\ UFCMA.cbad1{2} = cbad1_R + 1 /\\ t{2} = t0{2} /\\ x{2} = (n{2}, C.ofintd 0) /\\ x1{2} = x{2} /\\ exists (cbad1_L : int) (bad1_L : bool), UFCMA.bad1{1} = (bad1_L || (t0{1} \\in lt{1})) /\\ UFCMA.cbad1{1} = cbad1_L + 1 /\\ t{1} = t0{1} /\\ x{1} = (n{1}, C.ofintd 0) /\\ x1{1} = x{1} /\\ ((n{1} = n{2} /\\ a{1} = a{2} /\\ c1{1} = c1{2} /\\ lt{1} = lt{2} /\\ t0{1} = t0{2} /\\ p0{1} = p0{2} /\\ p{1} = p{2} /\\ Mem.log{1} = Mem.log{2} /\\ Mem.lc{1} = Mem.lc{2} /\\ BNR.lenc{1} = BNR.lenc{2} /\\ BNR.ndec{1} = BNR.ndec{2} /\\ UFCMA.log{1} = UFCMA.log{2} /\\ cbad1_L = cbad1_R /\\ RO.m{1} = RO.m{2} /\\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\\ SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\\ (uniq BNR.lenc{2} /\\ cbad1_R <= qenc /\\ size BNR.lenc{2} <= qenc /\\ size lbad1_R <= size (make_lbad1 UFCMA.log{2} Mem.lc{2} BNR.lenc{2}) <= qdec /\\ size Mem.lc{2} <= BNR.ndec{2} <= qdec /\\ uniq BNR.lenc{2} /\\ (forall (n1 : nonce), n1 \\in BNR.lenc{2} => let (a0, c3, t1) = oget UFCMA.log{2}.[n1] in (n1, a0, c3, t1) \\in Mem.log{2}) /\\ (forall (n1 : nonce), (n1 \\in BNR.lenc{2}) = (n1 \\in UFCMA.log{2})) /\\ forall (t1 t' : tag), (t1, t') \\in lbad1_R => exists (n1 : nonce), (n1 \\in BNR.lenc{2}) /\\ (oget UFCMA.log{2}.[n1]).`3 = t1 /\\ exists (a0 : associated_data) (c3 : message), (n1, a0, c3, t') \\in Mem.lc{2}) /\\ (bad1_L <=> exists (tt : tag * tag), (tt \\in lbad1_R) /\\ tt.`1 = tt.`2) /\\ check_plaintext BNR.lenc{1} p{1} /\\ n{1} = p{1}.`1 /\\ lt{2} = map (fun (c3 : ciphertext) => c3.`4) (filter (fun (c3 : ciphertext) => c3.`1 = n{2}) Mem.lc{2})) /\\ cbad1_L < qenc /\\ size lt{1} <= qdec) /\\ r{1} = r{2}","post":"post = (x1{2} \\notin RO.m{2} => (x1{1} \\notin RO.m{1} => (n{1} = n{2} /\\ a{1} = a{2} /\\ c1{1} = c1{2} /\\ t{1} = t{2}) /\\ (Mem.log{1}.[n{1}, a{1}, c1{1}, t{1} <- p0{1}] = Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}] /\\ Mem.lc{1} = Mem.lc{2} /\\ (p{1}.`1 = p{2}.`1 /\\ BNR.lenc{1} = BNR.lenc{2}) /\\ BNR.ndec{1} = BNR.ndec{2} /\\ UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] = UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] /\\ UFCMA.cbad1{1} = UFCMA.cbad1{2} /\\ RO.m{1}.[x1{1} <- r{2}] = RO.m{2}.[x1{2} <- r{2}] /\\ SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness] = SplitC2.I2.RO.m{2}.[n{2}, C.ofintd 0 <- witness] /\\ SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\\ ((! (p{2}.`1 \\in BNR.lenc{2}) /\\ uniq BNR.lenc{2}) /\\ UFCMA.cbad1{2} <= qenc /\\ 1 + size BNR.lenc{2} <= qenc /\\ (size UFCMA_l.lbad1{2} <= size (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2} (p{2}.`1 :: BNR.lenc{2})) /\\ (size UFCMA_l.lbad1{2} <= size (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2} (p{2}.`1 :: BNR.lenc{2})) => size (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2} (p{2}.`1 :: BNR.lenc{2})) <= qdec)) /\\ (size Mem.lc{2} <= BNR.ndec{2} /\\ (size Mem.lc{2} <= BNR.ndec{2} => BNR.ndec{2} <= qdec)) /\\ (! (p{2}.`1 \\in BNR.lenc{2}) /\\ uniq BNR.lenc{2}) /\\ (forall (n1 : nonce), n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2}) => forall (x10 : associated_data) (x2 : message) (x3 : tag), oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1] = (x10, x2, x3) => (n1, x10, x2, x3) \\in Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}]) /\\ (forall (n1 : nonce), (n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2})) = (n1 \\in UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})])) /\\ forall (t1 t' : tag), (t1, t') \\in UFCMA_l.lbad1{2} => exists (n1 : nonce), (n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2})) /\\ (oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1]).`3 = t1 /\\ exists (a0 : associated_data) (c3 : message), (n1, a0, c3, t') \\in Mem.lc{2}) /\\ (UFCMA.bad1{1} => exists (tt : tag * tag), (tt \\in UFCMA_l.lbad1{2}) /\\ tt.`1 = tt.`2) /\\ forall (tt : tag * tag), tt \\in UFCMA_l.lbad1{2} => tt.`1 = tt.`2 => UFCMA.bad1{1}) /\\ (x1{1} \\in RO.m{1} => (n{1} = n{2} /\\ a{1} = a{2} /\\ c1{1} = c1{2} /\\ t{1} = t{2}) /\\ (Mem.log{1}.[n{1}, a{1}, c1{1}, t{1} <- p0{1}] = Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}] /\\ Mem.lc{1} = Mem.lc{2} /\\ (p{1}.`1 = p{2}.`1 /\\ BNR.lenc{1} = BNR.lenc{2}) /\\ BNR.ndec{1} = BNR.ndec{2} /\\ UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] = UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] /\\ UFCMA.cbad1{1} = UFCMA.cbad1{2} /\\ RO.m{1} = RO.m{2}.[x1{2} <- r{2}] /\\ SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness] = SplitC2.I2.RO.m{2}.[n{2}, C.ofintd 0 <- witness] /\\ SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\\ ((! (p{2}.`1 \\in BNR.lenc{2}) /\\ uniq BNR.lenc{2}) /\\ UFCMA.cbad1{2} <= qenc /\\ 1 + size BNR.lenc{2} <= qenc /\\ (size UFCMA_l.lbad1{2} <= size (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2} (p{2}.`1 :: BNR.lenc{2})) /\\ (size UFCMA_l.lbad1{2} <= size (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2} (p{2}.`1 :: BNR.lenc{2})) => size (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2} (p{2}.`1 :: BNR.lenc{2})) <= qdec)) /\\ (size Mem.lc{2} <= BNR.ndec{2} /\\ (size Mem.lc{2} <= BNR.ndec{2} => BNR.ndec{2} <= qdec)) /\\ (! (p{2}.`1 \\in BNR.lenc{2}) /\\ uniq BNR.lenc{2}) /\\ (forall (n1 : nonce), n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2}) => forall (x10 : associated_data) (x2 : message) (x3 : tag), oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1] = (x10, x2, x3) => (n1, x10, x2, x3) \\in Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}]) /\\ (forall (n1 : nonce), (n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2})) = (n1 \\in UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})])) /\\ forall (t1 t' : tag), (t1, t') \\in UFCMA_l.lbad1{2} => exists (n1 : nonce), (n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2})) /\\ (oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1]).`3 = t1 /\\ exists (a0 : associated_data) (c3 : message), (n1, a0, c3, t') \\in Mem.lc{2}) /\\ (UFCMA.bad1{1} => exists (tt : tag * tag), (tt \\in UFCMA_l.lbad1{2}) /\\ tt.`1 = tt.`2) /\\ forall (tt : tag * tag), tt \\in UFCMA_l.lbad1{2} => tt.`1 = tt.`2 => UFCMA.bad1{1})) /\\ (x1{2} \\in RO.m{2} => (x1{1} \\notin RO.m{1} => (n{1} = n{2} /\\ a{1} = a{2} /\\ c1{1} = c1{2} /\\ t{1} = t{2}) /\\ (Mem.log{1}.[n{1}, a{1}, c1{1}, t{1} <- p0{1}] = Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}] /\\ Mem.lc{1} = Mem.lc{2} /\\ (p{1}.`1 = p{2}.`1 /\\ BNR.lenc{1} = BNR.lenc{2}) /\\ BNR.ndec{1} = BNR.ndec{2} /\\ UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] = UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] /\\ UFCMA.cbad1{1} = UFCMA.cbad1{2} /\\ RO.m{1}.[x1{1} <- r{2}] = RO.m{2} /\\ SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness] = SplitC2.I2.RO.m{2}.[n{2}, C.ofintd 0 <- witness] /\\ SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\\ ((! (p{2}.`1 \\in BNR.lenc{2}) /\\ uniq BNR.lenc{2}) /\\ UFCMA.cbad1{2} <= qenc /\\ 1 + size BNR.lenc{2} <= qenc /\\ (size UFCMA_l.lbad1{2} <= size (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2} (p{2}.`1 :: BNR.lenc{2})) /\\ (size UFCMA_l.lbad1{2} <= size (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2} (p{2}.`1 :: BNR.lenc{2})) => size (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2} (p{2}.`1 :: BNR.lenc{2})) <= qdec)) /\\ (size Mem.lc{2} <= BNR.ndec{2} /\\ (size Mem.lc{2} <= BNR.ndec{2} => BNR.ndec{2} <= qdec)) /\\ (! (p{2}.`1 \\in BNR.lenc{2}) /\\ uniq BNR.lenc{2}) /\\ (forall (n1 : nonce), n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2}) => forall (x10 : associated_data) (x2 : message) (x3 : tag), oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1] = (x10, x2, x3) => (n1, x10, x2, x3) \\in Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}]) /\\ (forall (n1 : nonce), (n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2})) = (n1 \\in UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})])) /\\ forall (t1 t' : tag), (t1, t') \\in UFCMA_l.lbad1{2} => exists (n1 : nonce), (n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2})) /\\ (oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1]).`3 = t1 /\\ exists (a0 : associated_data) (c3 : message), (n1, a0, c3, t') \\in Mem.lc{2}) /\\ (UFCMA.bad1{1} => exists (tt : tag * tag), (tt \\in UFCMA_l.lbad1{2}) /\\ tt.`1 = tt.`2) /\\ forall (tt : tag * tag), tt \\in UFCMA_l.lbad1{2} => tt.`1 = tt.`2 => UFCMA.bad1{1}) /\\ (x1{1} \\in RO.m{1} => (n{1} = n{2} /\\ a{1} = a{2} /\\ c1{1} = c1{2} /\\ t{1} = t{2}) /\\ (Mem.log{1}.[n{1}, a{1}, c1{1}, t{1} <- p0{1}] = Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}] /\\ Mem.lc{1} = Mem.lc{2} /\\ (p{1}.`1 = p{2}.`1 /\\ BNR.lenc{1} = BNR.lenc{2}) /\\ BNR.ndec{1} = BNR.ndec{2} /\\ UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] = UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] /\\ UFCMA.cbad1{1} = UFCMA.cbad1{2} /\\ RO.m{1} = RO.m{2} /\\ SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness] = SplitC2.I2.RO.m{2}.[n{2}, C.ofintd 0 <- witness] /\\ SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\\ ((! (p{2}.`1 \\in BNR.lenc{2}) /\\ uniq BNR.lenc{2}) /\\ UFCMA.cbad1{2} <= qenc /\\ 1 + size BNR.lenc{2} <= qenc /\\ (size UFCMA_l.lbad1{2} <= size (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2} (p{2}.`1 :: BNR.lenc{2})) /\\ (size UFCMA_l.lbad1{2} <= size (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2} (p{2}.`1 :: BNR.lenc{2})) => size (make_lbad1 UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] Mem.lc{2} (p{2}.`1 :: BNR.lenc{2})) <= qdec)) /\\ (size Mem.lc{2} <= BNR.ndec{2} /\\ (size Mem.lc{2} <= BNR.ndec{2} => BNR.ndec{2} <= qdec)) /\\ (! (p{2}.`1 \\in BNR.lenc{2}) /\\ uniq BNR.lenc{2}) /\\ (forall (n1 : nonce), n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2}) => forall (x10 : associated_data) (x2 : message) (x3 : tag), oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1] = (x10, x2, x3) => (n1, x10, x2, x3) \\in Mem.log{2}.[n{2}, a{2}, c1{2}, t{2} <- p0{2}]) /\\ (forall (n1 : nonce), (n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2})) = (n1 \\in UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})])) /\\ forall (t1 t' : tag), (t1, t') \\in UFCMA_l.lbad1{2} => exists (n1 : nonce), (n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2})) /\\ (oget UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})].[n1]).`3 = t1 /\\ exists (a0 : associated_data) (c3 : message), (n1, a0, c3, t') \\in Mem.lc{2}) /\\ (UFCMA.bad1{1} => exists (tt : tag * tag), (tt \\in UFCMA_l.lbad1{2}) /\\ tt.`1 = tt.`2) /\\ forall (tt : tag * tag), tt \\in UFCMA_l.lbad1{2} => tt.`1 = tt.`2 => UFCMA.bad1{1}))","remaining_goals_note":"You have 5 subgoals pending. The `goal_type` above is for the CURRENT (first pending) goal ONLY \u2014 the other 4 subgoal(s) may have DIFFERENT types. This is normal after tactics like `call (_: Inv)`, `byequiv`, `conseq`, or `seq K:` which each generate multiple subgoals with mixed pRHL/phoare/hoare/ambient shapes. Do NOT interpret a mismatch between the current-goal type and your proof plan as 'session is broken'. Close the current subgoal, then inspect the next one via `-goal-info` again. Use `-status` to see total proof progress.","remaining_goals_inference":[{"subgoal_n":1,"predicted_type":"(carried-over from earlier branching)","description":"Pending subgoal from a branching tactic earlier in history; this entry isn't from the latest `if.`. Run -goal-info on each subgoal as you reach it to see its actual shape.","origin_tactic":"(earlier branching, not tracked)"},{"subgoal_n":2,"predicted_type":"(carried-over from earlier branching)","description":"Pending subgoal from a branching tactic earlier in history; this entry isn't from the latest `if.`. Run -goal-info on each subgoal as you reach it to see its actual shape.","origin_tactic":"(earlier branching, not tracked)"},{"subgoal_n":3,"predicted_type":"(carried-over from earlier branching)","description":"Pending subgoal from a branching tactic earlier in history; this entry isn't from the latest `if.`. Run -goal-info on each subgoal as you reach it to see its actual shape.","origin_tactic":"(earlier branching, not tracked)"},{"subgoal_n":4,"predicted_type":"(inherits prior goal type)","description":"Then-branch (condition true)","origin_tactic":"if."},{"subgoal_n":5,"predicted_type":"(inherits prior goal type)","description":"Else-branch (condition false)","origin_tactic":"if."}],"remaining_goals_inference_caveat":"These subgoal shapes are INFERRED from the last branching tactic's known pattern, NOT read from EC directly (EC's emacs output only exposes the current goal). Use as hints, not ground truth. Ground truth is obtained by closing the current subgoal and running -goal-info on the next. Known-wrong cases: 3-arg `call (_: bad, Inv)`, nested branchers, while-variants with different arg counts."},"goal_state":{"state_kind":"open","goal_type":"pRHL","num_remaining":5,"num_remaining_determined":true,"proof_candidate_closed":false,"active_goal_hash":"6ebd969c125b5a0ec83fb4e05368232b83c61357","authority":"pretty_text_fallback","ec_ground_truth":false},"history":{"tactic_count":19,"has_qed":false,"latest_tactic":"rewrite /check_plaintext /=; smt(make_lbad1_size_cons3 leq_make_lbad1 size_cat size_map size_filter ge0_qdec ge0_qenc mem_cat mapP hasP mem_filter)."},"latest_transition":{"kind":"progress","status":"ok","goals_before":6,"goals_after":5,"candidate_closed":false,"no_progress":false,"tactic":"rewrite /check_plaintext /=; smt(make_lbad1_size_cons3 leq_make_lbad1 size_cat size_map size_filter ge0_qdec ge0_qenc mem_cat mapP hasP mem_filter)."},"items":[{"candidate":"Idiom: `rewrite /<op>; proc => /=; sp <L> <R>; if; 1:done; 2: by auto.` Use this when the residual is blocked on an opaque predicate rather than a missing subtype lemma.","why":"Oracle subgoal with a named-predicate invariant applied to relational state \u2014 smt() alone won't close because the op stays opaque","verification":"not daemon-verified against the current goal"},{"candidate":"Phase-ordering hint: a named oracle-equivalence handle, if present in the current context, usually applies while the oracle call is still a single frontier call. Inspect the current call handles/signatures first; use `call <oracle_equiv>` or `ecall (<oracle_equiv> <args>)` before inlining the call body. Inlining first can expand the call into several statements and make the named handle no longer directly callable. For residual branch or predicate obligations, combine the generic idioms `unfold_op_invariant_sp_if_done_auto` and `ecall_oracle_equiv_then_unfold_ambient_close` as needed. Run `-tactic-forms call` / `-where <oracle_equiv>` rather than guessing argument order.","why":"Oracle-state invariant maintenance with multiple live maps/logs/counters on both sides","verification":"not daemon-verified against the current goal"}],"notes":[{"message":"You have 5 subgoals pending. The `goal_type` above is for the CURRENT (first pending) goal ONLY \u2014 the other 4 subgoal(s) may have DIFFERENT types. This is normal after tactics like `call (_: Inv)`, `byequiv`, `conseq`, or `seq K:` which each generate multiple subgoals with mixed pRHL/phoare/hoare/ambient shapes. Do NOT interpret a mismatch between the current-goal type and your proof plan as 'session is broken'. Close the current subgoal, then inspect the next one via `-goal-info` again. Use `-status` to see total proof progress."}]}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_1_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_1_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_1_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_1_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
