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
[SKELETON-HITS] `search (+^)` -> 91 lemma(s)
  (broad result — to get the applicable lemma on top, search a TERM SKELETON of the sub-term you are rewriting, e.g. `(big _ _ (_ :: _))` or `(_ ++ _)`, not the bare operator)

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

lemma big_rem ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s : 'a list) (x : 'a),
    x \in s => big P F s = (if P x then F x else zerow) +^ big P F (rem x s).

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

lemma big_nseq_cond ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (n : int) (x : 'a),
    big P F (nseq n x) = if P x then iter n ((+^) (F x)) zerow else zerow.

lemma big_nseq ['a]:
  forall (F : 'a -> word) (n : int) (x : 'a),
    big predT<:'a> F (nseq n x) = iter n ((+^) (F x)) zerow.

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

lemma big_cat_int:
  forall (n m p : int) (P : int -> bool) (F : int -> word),
    m <= n => n <= p => bigi P F m p = bigi P F m n +^ bigi P F n p.

lemma big_cat ['a]:
  forall (P : 'a -> bool) (F : 'a -> word) (s1 s2 : 'a list),
    big P F (s1 ++ s2) = big P F s1 +^ big P F s2.

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

(* WRing.AddMonoid.iteropE *)
lemma iteropE:
  forall (n : int) (x : WRing.t),
    iterop n (+^) x zerow = iter n ((+^) x) zerow.

(* WRing.AddMonoid.addmCA *)
lemma addmCA: left_commutative (+^).

(* WRing.AddMonoid.addmC *)
lemma addmC: commutative (+^).

(* WRing.AddMonoid.addmACA *)
lemma addmACA: interchange (+^) (+^).

(* WRing.AddMonoid.addmAC *)
lemma addmAC: right_commutative (+^).

(* WRing.AddMonoid.addmA *)
lemma addmA: associative (+^).

(* WRing.AddMonoid.addm0 *)
lemma addm0: right_id zerow (+^).

(* WRing.AddMonoid.add0m *)
lemma add0m: left_id zerow (+^).

(* WRing.subrr *)
lemma subrr: forall (x : WRing.t), WRing.(-) x x = zerow.

(* WRing.subr_sqr_1 *)
lemma subr_sqr_1:
  forall (x : WRing.t),
    WRing.(-) (WRing.exp x 2) onew = andw (WRing.(-) x onew) (x +^ onew).

(* WRing.subr_eq0 *)
lemma subr_eq0: forall (x y : WRing.t), WRing.(-) x y = zerow <=> x = y.

(* WRing.subr_eq *)
lemma subr_eq: forall (x y z : WRing.t), WRing.(-) x z = y <=> x = y +^ z.

(* WRing.subr_add2r *)
lemma subr_add2r:
  forall (z x y : WRing.t), WRing.(-) (x +^ z) (y +^ z) = WRing.(-) x y.

(* WRing.subrK *)
lemma subrK: forall (x y : WRing.t), WRing.(-) x y +^ y = x.

(* WRing.subrACA *)
lemma subrACA: interchange (fun (x y : WRing.t) => WRing.(-) x y) (+^).

(* WRing.subr0 *)
lemma subr0: forall (x : WRing.t), WRing.(-) x zerow = x.

(* WRing.sub0r *)
lemma sub0r: forall (x : WRing.t), WRing.(-) zerow x = oppw x.

(* WRing.sqrrD *)
lemma sqrrD:
  forall (x y : WRing.t),
    WRing.exp (x +^ y) 2 =
    WRing.exp x 2 +^ WRing.intmul (andw x y) 2 +^ WRing.exp y 2.

(* WRing.sqrrB *)
lemma sqrrB:
  forall (x y : WRing.t),
    WRing.exp (WRing.(-) x y) 2 =
    WRing.(-) (WRing.exp x 2) (WRing.intmul (andw x y) 2) +^ WRing.exp y 2.

(* WRing.opprD *)
lemma opprD: forall (x y : WRing.t), oppw (x +^ y) = WRing.(-) (oppw x) y.

(* WRing.opprB *)
lemma opprB: forall (x y : WRing.t), oppw (WRing.(-) x y) = WRing.(-) y x.

(* WRing.ofintS *)
lemma ofintS:
  forall (i : int), 0 <= i => WRing.ofint (i + 1) = onew +^ WRing.ofint i.

(* WRing.mulrSz *)
lemma mulrSz:
  forall (x : WRing.t) (n : int),
    WRing.intmul x (n + 1) = x +^ WRing.intmul x n.

(* WRing.mulrSl *)
lemma mulrSl: forall (x y : WRing.t), andw (x +^ onew) y = andw x y +^ y.

(* WRing.mulrS *)
lemma mulrS:
  forall (x : WRing.t) (n : int),
    0 <= n => WRing.intmul x (n + 1) = x +^ WRing.intmul x n.

(* WRing.mulrDz *)
lemma mulrDz:
  forall (x : WRing.t) (n m : int),
    WRing.intmul x (n + m) = WRing.intmul x n +^ WRing.intmul x m.

(* WRing.mulrDr *)
lemma mulrDr: right_distributive andw (+^).

(* WRing.mulrDl *)
lemma mulrDl: left_distributive andw (+^).

(* WRing.mulrBr *)
lemma mulrBr: right_distributive andw (fun (x y : WRing.t) => WRing.(-) x y).

(* WRing.mulrBl *)
lemma mulrBl: left_distributive andw (fun (x y : WRing.t) => WRing.(-) x y).

(* WRing.mulr2z *)
lemma mulr2z: forall (x : WRing.t), WRing.intmul x 2 = x +^ x.

(* WRing.mul1r2z *)
lemma mul1r2z: forall (x : WRing.t), andw x (WRing.ofint 2) = x +^ x.

(* WRing.intmulpE *)
lemma intmulpE:
  forall (z : WRing.t) (c : int),
    0 <= c => WRing.intmul z c = iterop c (+^) z zerow.

(* WRing.fracrDE *)
lemma fracrDE:
  forall (n1 n2 d1 d2 : WRing.t),
    unitw d1 =>
    unitw d2 =>
    WRing.(/) n1 d1 +^ WRing.(/) n2 d2 =
    WRing.(/) (andw n1 d2 +^ andw n2 d1) (andw d1 d2).

(* WRing.eqr_sub *)
lemma eqr_sub:
  forall (x y z t : WRing.t),
    WRing.(-) x y = WRing.(-) z t <=> x +^ t = z +^ y.

(* WRing.addrr *)
lemma addrr: forall (x : WRing.t), x +^ x = zerow.

(* WRing.addr_eq0 *)
lemma addr_eq0: forall (x y : WRing.t), x +^ y = zerow <=> x = oppw y.

(* WRing.addrNK *)
lemma addrNK: rev_right_loop oppw (+^).

(* WRing.addrN *)
lemma addrN: right_inverse zerow oppw (+^).

(* WRing.addrK *)
lemma addrK: right_loop oppw (+^).

(* WRing.addrI *)
lemma addrI: right_injective (+^).

(* WRing.addrCA *)
lemma addrCA: left_commutative (+^).

(* WRing.addrC *)
lemma addrC: commutative (+^).

(* WRing.addrACA *)
lemma addrACA: interchange (+^) (+^).

(* WRing.addrAC *)
lemma addrAC: right_commutative (+^).

(* WRing.addrA *)
lemma addrA: associative (+^).

(* WRing.addr0 *)
lemma addr0: right_id zerow (+^).

(* WRing.addNr *)
lemma addNr: left_inverse zerow oppw (+^).

(* WRing.addNKr *)
lemma addNKr: rev_left_loop oppw (+^).

(* WRing.addKr *)
lemma addKr: left_loop oppw (+^).

(* WRing.addIr *)
lemma addIr: left_injective (+^).

(* WRing.add0r *)
lemma add0r: left_id zerow (+^).

lemma xorwK: forall (x : word), x +^ x = zerow.

lemma xorwE:
  forall (w1 w2 : word) (i : int), (w1 +^ w2).[i] = w1.[i] ^^ w2.[i].

lemma xorwC: commutative (+^).

lemma xorwA: associative (+^).

lemma xorw0: right_id zerow (+^).

lemma andwDl: left_distributive andw (+^).

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