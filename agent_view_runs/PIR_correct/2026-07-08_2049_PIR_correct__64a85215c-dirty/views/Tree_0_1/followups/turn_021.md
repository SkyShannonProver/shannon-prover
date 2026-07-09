## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
i0: int
hi: 0 <= i0 < N
&hr: {b : bool, i, j : int, s, s0 : int list, r, r' : word}
Hi0: i{hr} = i0
------------------------------------------------------------------------
forall (s1 s' : int list) (j0 : int),
  (0 <= j0 <= N /\
   i{hr} = i0 /\ (j0 <= i0 => s1 = s') /\ (i0 < j0 => sxor2 s1 s' i0) =>
   N - j0 <= 0 => ! j0 < N) /\
  (! j0 < N =>
   0 <= j0 <= N /\
   i{hr} = i0 /\ (j0 <= i0 => s1 = s') /\ (i0 < j0 => sxor2 s1 s' i0) =>
   big predT<:int> a s1 +^ big predT<:int> a s' = a i0)
[35|check]>
```

---

## Pure Logic Residual

**Conclusion obligations:**
- `equality obligation: forall (s1 s' : int list) (j0 : int), (0 <= j0 <= N /\ i{hr} = i0 /\ (j0 <= i0 => s1 = s') /\ (i0 < j0 => sxor2 s1 s' i0) => N - j0 <= 0 => ! j0 < N)`
- `equality obligation: (! j0 < N => 0 <= j0 <= N /\ i{hr} = i0 /\ (j0 <= i0 => s1 = s') /\ (i0 < j0 => sxor2 s1 s' i0) => big predT<:int> a s1 +^ big predT<:int> a s' = a i0)`

**Memory-decorated terms:** `terms: i{hr}; introduced memory: &hr, &m`

---

## Status
remaining **1** · phase `pure_logic`

---

### Need more? submit one read-only request
- `operator_lemmas` (+operator); operator choices: `(+^)`, `sxor2`, `big`, `predT`
  submit `{"intent": "operator_lemmas", "payload": {"operator": "<operator>"}}`
- `tactic_forms` (+name); name choices: `rewrite`
  submit `{"intent": "tactic_forms", "payload": {"name": "<name>"}}`

---

## Read-only result
## Requested: `operator_lemmas`

**Returned text:**
```text
[SKELETON-HITS] `search big` -> 75 lemma(s)
  (broad result — to get the applicable lemma on top, search a TERM SKELETON of the sub-term you are rewriting, e.g. `(big _ _ (_ :: _))` or `(_ ++ _)`, not the bare operator)

lemma partition_big ['a, 'b]:
  forall (px : 'a -> 'b) (P : 'a -> bool) (Q : 'b -> bool) (F : 'a -> word)
    (s : 'a list) (s' : 'b list),
    uniq s' =>
    (forall (x : 'a), x \in s => P x => (px x \in s') /\ Q (px x)) =>
    big P F s =
    big Q (fun (x : 'b) => big (fun (y : 'a) => P y /\ px y = x) F s) s'.

lemma exchange_big ['a, 'b]:
  forall (P1 : 'a -> bool) (P2 : 'b -> bool) (F : 'a -> 'b -> word)
    (s1 : 'a list) (s2 : 'b list),
    big P1 (fun (a : 'a) => big P2 (F a) s2) s1 =
    big P2 (fun (b : 'b) => big P1 (fun (a : 'a) => F a b) s1) s2.

lemma eq_bigr ['a]:
  forall (P : 'a -> bool) (F1 F2 : 'a -> word) (s : 'a list),
    (forall (i : 'a), P i => F1 i = F2 i) => big P F1 s = big P F2 s.

lemma eq_bigl ['a]:
  forall (P1 P2 : 'a -> bool) (F : 'a -> word) (s : 'a list),
    (forall (i : 'a), P1 i <=> P2 i) => big P1 F s = big P2 F s.

lemma eq_big_seq ['a]:
  forall (F1 F2 : 'a -> word) (s : 'a list),
    (forall (x : 'a), x \in s => F1 x = F2 x) =>
    big predT<:'a> F1 s = big predT<:'a> F2 s.

lemma eq_big_perm_map ['a]:
  forall (F : 'a -> word) (s1 s2 : 'a list),
    perm_eq (map F s1) (map F s2) =>
    big predT<:'a> F s1 = big predT<:'a> F s2.

lemma eq_big_perm ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s1 s2 : 'a list),
    perm_eq s1 s2 => big P F s1 = big P F s2.

lemma eq_big_int:
  forall (m n : int) (F1 F2 : int -> word),
    (forall (i : int), m <= i < n => F1 i = F2 i) =>
    bigi predT<:int> F1 m n = bigi predT<:int> F2 m n.

lemma eq_big ['a]:
  forall (P1 P2 : 'a -> bool) (F1 F2 : 'a -> word) (s : 'a list),
    (forall (i : 'a), P1 i <=> P2 i) =>
    (forall (i : 'a), P1 i => F1 i = F2 i) => big P1 F1 s = big P2 F2 s.

lemma congr_big_seq ['a]:
  forall (P1 P2 : 'a -> bool) (F1 F2 : 'a -> word) (s : 'a list),
    (forall (x : 'a), x \in s => P1 x = P2 x) =>
    (forall (x : 'a), x \in s => P1 x => P2 x => F1 x = F2 x) =>
    big P1 F1 s = big P2 F2 s.

lemma congr_big_int:
  forall (m1 n1 m2 n2 : int) (P1 P2 : int -> bool) (F1 F2 : int -> word),
    m1 = m2 =>
    n1 = n2 =>
    (forall (i : int), m1 <= i < n2 => P1 i = P2 i) =>
    (forall (i : int), P1 i /\ m1 <= i < n2 => F1 i = F2 i) =>
    bigi P1 F1 m1 n1 = bigi P2 F2 m2 n2.

lemma congr_big ['a]:
  forall (r1 r2 : 'a list) (P1 P2 : 'a -> bool) (F1 F2 : 'a -> word),
    r1 = r2 =>
    (forall (x : 'a), P1 x <=> P2 x) =>
    (forall (i : 'a), P1 i => F1 i = F2 i) => big P1 F1 r1 = big P2 F2 r2.

lemma bigi_split_odd_even:
  forall (n : int) (F : int -> word),
    0 <= n =>
    bigi predT<:int> (fun (i : int) => F (2 * i) +^ F (2 * i + 1)) 0 n =
    bigi predT<:int> F 0 (2 * n).

lemma big_undup ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list),
    big P F s =
    big P (fun (a : 'a) => iter (count (pred1 a) s) ((+^) (F a)) zerow)
      (undup s).

lemma big_split ['a]:
  forall (P : 'a -> bool) (F1 F2 : 'a -> word) (s : 'a list),
    big P (fun (i : 'a) => F1 i +^ F2 i) s = big P F1 s +^ big P F2 s.

lemma big_seq_cond ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list),
    big P F s = big (fun (i : 'a) => (i \in s) /\ P i) F s.

lemma big_seq1 ['a]:
  forall (F : 'a -> word) (x : 'a), big predT<:'a> F [x] = F x.

lemma big_seq ['a]:
  forall (F : 'a -> word) (s : 'a list),
    big predT<:'a> F s = big (fun (i : 'a) => i \in s) F s.

lemma big_rem ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list) (x : 'a),
    x \in s => big P F s = (if P x then F x else zerow) +^ big P F (rem x s).

lemma big_reindex ['a, 'b]:
  forall (P : 'a -> bool) (F : 'a -> word) (f : 'b -> 'a) (f' : 'a -> 'b)
    (s : 'a list),
    (forall (x : 'a), x \in s => f (f' x) = x) =>
    big P F s = big (P \o f) (F \o f) (map f' s).

lemma big_rec2 ['a]:
  forall (K : word -> word -> bool) (r : 'a list) (P : 'a -> bool) (F1
    F2 : 'a -> word),
    K zerow zerow =>
    (forall (i : 'a) (y1 y2 : word),
       P i => K y1 y2 => K (F1 i +^ y1) (F2 i +^ y2)) =>
    K (big P F1 r) (big P F2 r).

lemma big_rec ['a]:
  forall (K : word -> bool) (r : 'a list) (P : 'a -> bool) (F : 'a -> word),
    K zerow =>
    (forall (i : 'a) (x : word), P i => K x => K (F i +^ x)) => K (big P F r).

lemma big_rcons ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list) (x : 'a),
    big P F (rcons s x) = if P x then big P F s +^ F x else big P F s.

lemma big_pred0_eq ['a]:
  forall (F : 'a -> word) (s : 'a list), big pred0<:'a> F s = zerow.

lemma big_pred0 ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list),
    (forall (i : 'a), P i <=> false) => big P F s = zerow.

lemma big_pair_pswap ['a, 'b]:
  forall (p : 'a * 'b -> bool) (f : 'a * 'b -> word) (s : ('a * 'b) list),
    big p f s =
    big (p \o pswap<:'b, 'a>) (f \o pswap<:'b, 'a>) (map pswap<:'a, 'b> s).

lemma big_pair ['a, 'b]:
  forall (F : 'a * 'b -> word) (s : ('a * 'b) list),
    uniq s =>
    big predT<:'a * 'b> F s =
    big predT<:'a>
      (fun (a : 'a) =>
         big predT<:'a * 'b> F (filter (fun (xy : 'a * 'b) => xy.`1 = a) s))
      (undup (unzip1 s)).

lemma big_nth ['a]:
  forall (x0 : 'a) (P : 'a -> bool) (F : 'a -> word) (s : 'a list),
    big P F s = bigi (P \o nth x0 s) (F \o nth x0 s) 0 (size s).

lemma big_nseq_cond ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (n : int) (x : 'a),
    big P F (nseq n x) = if P x then iter n ((+^) (F x)) zerow else zerow.

lemma big_nseq ['a]:
  forall (F : 'a -> word) (n : int) (x : 'a),
    big predT<:'a> F (nseq n x) = iter n ((+^) (F x)) zerow.

lemma big_nil ['a]:
  forall (P : 'a -> bool) (F : 'a -> word), big P F [] = zerow.

lemma big_mkcond ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list),
    big P F s = big predT<:'a> (fun (i : 'a) => if P i then F i else zerow) s.

lemma big_mapT ['a, 'b]:
  forall (h : 'b -> 'a) (F : 'a -> word) (s : 'b list),
    big predT<:'a> F (map h s) = big predT<:'b> (F \o h) s.

lemma big_map ['a, 'b]:
  forall (h : 'b -> 'a) (P : 'a -> bool) (F : 'a -> word) (s : 'b list),
    big P F (map h s) = big (P \o h) (F \o h) s.

lemma big_ltn_cond:
  forall (m n : int) (P : int -> bool) (F : int -> word),
    m < n =>
    let x = bigi P F (m + 1) n in bigi P F m n = if P m then F m +^ x else x.

lemma big_ltn:
  forall (m n : int) (F : int -> word),
    m < n => bigi predT<:int> F m n = F m +^ bigi predT<:int> F (m + 1) n.

lemma big_int_recr_cond:
  forall (n m : int) (P : int -> bool) (F : int -> word),
    m <= n => bigi P F m (n + 1) = bigi P F m n +^ if P n then F n else zerow.

lemma big_int_recr:
  forall (n m : int) (F : int -> word),
    m <= n => bigi predT<:int> F m (n + 1) = bigi predT<:int> F m n +^ F n.

lemma big_int_recl_cond:
  forall (n m : int) (P : int -> bool) (F : int -> word),
    m <= n =>
    bigi P F m (n + 1) =
    (if P m then F m else zerow) +^
    bigi (fun (i : int) => P (i + 1)) (fun (i : int) => F (i + 1)) m n.

lemma big_int_recl:
  forall (n m : int) (F : int -> word),
    m <= n =>
    bigi predT<:int> F m (n + 1) =
    F m +^ bigi predT<:int> (fun (i : int) => F (i + 1)) m n.

lemma big_int_cond:
  forall (m n : int) (P : int -> bool) (F : int -> word),
    bigi P F m n = bigi (fun (i : int) => m <= i < n /\ P i) F m n.

lemma big_int1:
  forall (n : int) (F : int -> word), bigi predT<:int> F n (n + 1) = F n.

lemma big_int:
  forall (m n : int) (F : int -> word),
    bigi predT<:int> F m n = bigi (fun (i : int) => m <= i < n) F m n.

lemma big_ind2 ['a]:
  forall (K : word -> word -> bool) (r : 'a list) (P : 'a -> bool) (F1
    F2 : 'a -> word),
    (forall (x1 x2 y1 y2 : word),
       K x1 x2 => K y1 y2 => K (x1 +^ y1) (x2 +^ y2)) =>
    K zerow zerow =>
    (forall (i : 'a), P i => K (F1 i) (F2 i)) => K (big P F1 r) (big P F2 r).

lemma big_ind ['a]:
  forall (K : word -> bool) (r : 'a list) (P : 'a -> bool) (F : 'a -> word),
    (forall (x y : word), K x => K y => K (x +^ y)) =>
    K zerow => (forall (i : 'a), P i => K (F i)) => K (big P F r).

lemma big_hasC ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list),
    ! has P s => big P F s = zerow.

lemma big_geq:
  forall (m n : int) (P : int -> bool) (F : int -> word),
    n <= m => bigi P F m n = zerow.

lemma big_flatten ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (rr : 'a list list),
    big P F (flatten rr) =
    big predT<:'a list> (fun (s : 'a list) => big P F s) rr.

lemma big_filter_cond ['a]:
  forall (P1 P2 : 'a -> bool) (F : 'a -> word) (s : 'a list),
    big P2 F (filter P1 s) = big (predI P1 P2) F s.

lemma big_filter ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list),
    big predT<:'a> F (filter P s) = big P F s.

lemma big_eq_idm_filter ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list),
    (forall (x : 'a), ! P x => F x = zerow) => big predT<:'a> F s = big P F s.

lemma big_endo ['a]:
  forall (f : word -> word),
    f zerow = zerow =>
    (forall (x y : word), f (x +^ y) = f x +^ f y) =>
    forall (r : 'a list) (P : 'a -> bool) (F : 'a -> word),
      f (big P F r) = big P (f \o F) r.

lemma big_distrr ['a]:
  forall (op_ : word -> word -> word) (P : 'a -> bool) (F : 'a -> word)
    (s : 'a list) (t : word),
    right_zero zerow op_ =>
    right_distributive op_ (+^) =>
    op_ t (big P F s) = big P (fun (a : 'a) => op_ t (F a)) s.

lemma big_distrl ['a]:
  forall (op_ : word -> word -> word) (P : 'a -> bool) (F : 'a -> word)
    (s : 'a list) (t : word),
    left_zero zerow op_ =>
    left_distributive op_ (+^) =>
    op_ (big P F s) t = big P (fun (a : 'a) => op_ (F a) t) s.

lemma big_distr ['a, 'b]:
  forall (op_ : word -> word -> word) (P1 : 'a -> bool) (P2 : 'b -> bool)
    (F1 : 'a -> word) (s1 : 'a list) (F2 : 'b -> word) (s2 : 'b list),
    commutative op_ =>
    left_zero zerow op_ =>
    left_distributive op_ (+^) =>
    op_ (big P1 F1 s1) (big P2 F2 s2) =
    big P1
      (fun (a1 : 'a) => big P2 (fun (a2 : 'b) => op_ (F1 a1) (F2 a2)) s2) s1.

lemma big_const ['a]:
  forall (P : 'a -> bool) (x : word) (s : 'a list),
    big P (fun (_ : 'a) => x) s = iter (count P s) ((+^) x) zerow.

lemma big_consT ['a]:
  forall (F : 'a -> word) (x : 'a) (s : 'a list),
    big predT<:'a> F (x :: s) = F x +^ big predT<:'a> F s.

lemma big_cons ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (x : 'a) (s : 'a list),
    big P F (x :: s) = if P x then F x +^ big P F s else big P F s.

lemma big_comp ['a]:
  forall (h : word -> word) (P : 'a -> bool) (F : 'a -> word) (s : 'a list),
    h zerow = zerow =>
    morphism_2 h (+^) (+^) => h (big P F s) = big P (h \o F) s.

lemma big_catr ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s1 s2 : 'a list),
    ! has P s1 => big P F (s1 ++ s2) = big P F s2.

lemma big_catl ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s1 s2 : 'a list),
    ! has P s2 => big P F (s1 ++ s2) = big P F s1.

lemma big_cat_int:
  forall (n m p : int) (P : int -> bool) (F : int -> word),
    m <= n => n <= p => bigi P F m p = bigi P F m n +^ bigi P F n p.

lemma big_cat ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s1 s2 : 'a list),
    big P F (s1 ++ s2) = big P F s1 +^ big P F s2.

lemma big_andbC ['a]:
  forall (P Q : 'a -> bool) (F : 'a -> word) (s : 'a list),
    big (fun (x : 'a) => P x /\ Q x) F s =
    big (fun (x : 'a) => Q x /\ P x) F s.

lemma big_allpairs ['a, 'b, 'c]:
  forall (f : 'a -> 'b -> 'c) (F : 'c -> word) (s : 'a list) (t : 'b list),
    big predT<:'c> F (allpairs f s t) =
    big predT<:'a>
      (fun (x : 'a) => big predT<:'b> (fun (y : 'b) => F (f x y)) t) s.

lemma big_addn:
  forall (m n a : int) (P : int -> bool) (F : int -> word),
    bigi P F (m + a) n =
    bigi (fun (i : int) => P (i + a)) (fun (i : int) => F (i + a)) m (n - a).

lemma bigU ['a]:
  forall (P Q : 'a -> bool) (F : 'a -> word) (s : 'a list),
    (forall (x : 'a), ! (P x /\ Q x)) =>
    big (predU P Q) F s = big P F s +^ big Q F s.

lemma bigID ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (a : 'a -> bool) (s : 'a list),
    big P F s = big (predI P a) F s +^ big (predI P (predC a)) F s.

lemma bigEM ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list),
    big predT<:'a> F s = big P F s +^ big (predC P) F s.

lemma bigD1_cond_if ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list) (x : 'a),
    uniq s =>
    big P F s =
    (if (x \in s) /\ P x then F x else zerow) +^ big (predI P (predC1 x)) F s.

lemma bigD1_cond ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list) (x : 'a),
    P x =>
    x \in s => uniq s => big P F s = F x +^ big (predI P (predC1 x)) F s.

lemma bigD1 ['a]:
  forall (F : 'a -> word) (s : 'a list) (x : 'a),
    x \in s => uniq s => big predT<:'a> F s = F x +^ big (predC1 x) F s.

lemma big1_seq ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list),
    (forall (i : 'a), P i /\ (i \in s) => F i = zerow) => big P F s = zerow.

lemma big1_eq ['a]:
  forall (P : 'a -> bool) (s : 'a list),
    big P (fun (_ : 'a) => zerow) s = zerow.

lemma big1 ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list),
    (forall (i : 'a), P i => F i = zerow) => big P F s = zerow.

Current goal

Type variables: <none>

&m: {}
i0: int
------------------------------------------------------------------------
0 <= i0 < N => Pr[PIR.main(i0) @ &m : res = a i0] = 1%r
```

**Notes:**
- `message`: Lookup result is recorded as raw/context evidence.

---

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

The current goal is shown in full above. If context is compacted or this response is truncated, re-read `LEGAL_LATEST_FOLLOWUP` for the same agent-readable surface; the raw workspace JSON is audit-only.