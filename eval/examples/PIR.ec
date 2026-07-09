require import AllCore Distr Bool DBool DInterval List.

require BitWord Bigop.

clone import BitWord as BS.
clone import Bigop as BBS with
   type t <- BS.word,
   op Support.idm <- BS.zerow,
   op Support.( + ) <- BS.(+^)
   proof * by smt(xorwA xorwC xorw0).

op N:int.

pred sxor (s s':int list) (i:int) =
  exists s1 s2, s = s1 ++ s2 /\ s' = s1 ++ i :: s2.

pred sxor2 (s s':int list) (i:int) =
  sxor s s' i \/ sxor s' s i.

lemma sxor_cons s i : sxor s (i :: s) i.
proof. by exists [] s. qed.

lemma sxor2_cons (s s':int list) (i j:int):
  sxor2 s s' i => sxor2 (j::s) (j::s') i.
proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    case=> -[s1 s2 [-> ->]]; [left | right]; exists (j::s1) s2 => //.
qed.

(* The database *)
op a : int -> word.

module PIR = {

  proc query (s:int list) = {
    return (big predT a s);
  }

  var s, s' : int list

  proc main (i:int) = {
    var r, r' : word;
    var j <- 0;

    var b;

    (s, s') <- ([], []);
    while (j < N) {
      b <$ {0,1};
      if (j = i) {
        if (b) s <- j :: s; else s' <- j :: s';
      } else {
        if (b) { s <- j :: s; s' <- j :: s'; }
      }
      j <- j + 1;
    }

    r <@ query(s);
    r' <@ query(s');

    return r +^ r';
  }

}.

lemma PIR_correct &m i0 : 0 <= i0 < N => Pr [PIR.main(i0) @ &m : res = a i0] = 1%r.
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  move => H_range.
  byphoare (_: i = i0 /\ 0 <= i0 < N ==> _) => //.
  proc; inline *; wp; sp.
  while (big predT a PIR.s +^ big predT a PIR.s' = (if i0 < j then a i0 else zerow) /\ 0 <= j <= N /\ i = i0 /\ 0 <= i0 < N) (N - j).
  auto.
  move=> &hr [[[[Hinv [Hj [-> Hi0]]] HjN] Hvar] _]; split; first by rewrite dbool_ll.
  move=> _ v _; rewrite /predT; case (j{hr} = i0) => [Heq | Hneq].
  rewrite Heq.
  move: Hinv; rewrite Heq => Hinv.
  move: Hvar; rewrite Heq => Hvar.
  move: Hinv; rewrite ltzz /= => Hinv.
  rewrite ltzS lezz /=.
  rewrite !big_consT.
  case v => _.
  have -> : big (fun (_ : int) => true) a PIR.s'{hr} = big predT a PIR.s'{hr} by rewrite /predT.
  rewrite -xorwA Hinv xorw0.
  smt().
  have -> : big (fun (_ : int) => true) a PIR.s'{hr} = big predT a PIR.s'{hr} by rewrite /predT.
  have -> : big (fun (_ : int) => true) a PIR.s{hr} = big predT a PIR.s{hr} by rewrite /predT.
  rewrite xorwA (xorwC (big predT<:int> a PIR.s{hr})) -xorwA Hinv xorw0.
  smt().
  split => [_ | //]; simplify.
  have -> : (i0 < j{hr} + 1) = (i0 < j{hr}) by smt().
  case v => _.
  rewrite !big_consT.
  smt(xorwA xorwC xorwK xorw0).
  have -> : big (fun (_ : int) => true) a PIR.s{hr} = big predT a PIR.s{hr} by rewrite /predT.
  have -> : big (fun (_ : int) => true) a PIR.s'{hr} = big predT a PIR.s'{hr} by rewrite /predT.
  rewrite Hinv; smt().
  auto.
  move=> &hr [-> [-> [-> [-> Hi0]]]].
  rewrite !big_nil xorw0; smt().
qed.

equiv PIR_secure1: PIR.main ~ PIR.main : true ==> ={PIR.s}.
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  proc; inline *; wp.
  while (={PIR.s, j}); auto; smt(dbool_funi).
qed.

hint exact : dbool_funi.
hint exact : dbool_fu.

equiv PIR_secure2: PIR.main ~ PIR.main : true ==> ={PIR.s'}.
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  proc. inline *. wp.
  while (={PIR.s', j}).
  wp; rnd (fun b => if (j{1} = i{1}) = (j{2} = i{2}) then b else !b).
  skip => /> /#.
  auto.
qed.

lemma PIR_secuity_s_byequiv i1 i2 &m1 &m2 x:
   Pr[PIR.main(i1) @ &m1 : PIR.s = x] = Pr[PIR.main(i2) @ &m2 : PIR.s = x].
proof. by byequiv PIR_secure1. qed.

lemma PIR_secuity_s'_byequiv i1 i2 &m1 &m2 x:
   Pr[PIR.main(i1) @ &m1 : PIR.s' = x] = Pr[PIR.main(i2) @ &m2 : PIR.s' = x].
proof. by byequiv PIR_secure2. qed.

(* ************************************************************************** *)
(* Alternative proof:                                                         *)
(*   We show that the distribution of PIR.s and PIR.s' is uniform             *)
(* First version we use phoare                                                *)

require import List FSet.

op restr (s : int fset) n =
 s `&` oflist (iota_ 0 n).

op is_restr (s : int fset) n =
  s = restr s n.

lemma restrS s j : 0 <= j =>
  restr  s (j + 1) =
  (if (j \in s) then fset1 j else fset0) `|` restr s j.
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  (* fsetP extensionality with iota rewriting *)
  admit.
qed.

lemma nin_is_restr n s : is_restr s n => !n \in s.
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  by move=> hs; smt(in_fsetI mem_oflist mem_iota).
qed.

(* TODO: rename mem_oflist in in_oflist *)
lemma is_restr_diff n s1 s2 : is_restr s2 n => fset1 n `|` s1 <> s2.
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  move=> /nin_is_restr hn; apply/negP=> h; move: hn.
  by rewrite -h in_fsetU in_fset1.
qed.

lemma is_restr_Ueq n s1 s2 :
  is_restr s1 n => is_restr s2 n =>
  (fset1 n `|` s1 =  fset1 n `|` s2) = (s1 = s2).
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  move=> h1 h2; rewrite eq_iff; split=> [h|->] //.
  apply fsetP=> x; have /fsetP hx := h.
  move: (hx x); rewrite !in_fsetU !in_fset1.
  have ? := nin_is_restr n s1 h1.
  have ? := nin_is_restr n s2 h2.
  smt().
qed.

lemma is_restr_addS n s :
  0 <= n =>
  is_restr s n => is_restr (fset1 n `|` s) (n + 1).
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  (* fset extensionality *)
  move=> hn hs; rewrite /is_restr; apply fsetP => x.
  rewrite /restr in_fsetI in_fsetU in_fset1 mem_oflist mem_iota.
  have /fsetP /(_ x) := hs.
  rewrite /restr in_fsetI mem_oflist mem_iota.
  smt().
qed.

lemma is_restrS n s :
  0 <= n =>
  is_restr s n => is_restr s (n + 1).
proof.
  by move=> Hn Hs; rewrite /is_restr restrS // (@nin_is_restr _ _ Hs) /= fset0U.
qed.

lemma is_restr_restr n s : is_restr (restr s n) n.
proof.
  apply fsetP => x;rewrite /restr !in_fsetI !mem_oflist /#.
qed.

lemma is_restr_fset0 n : is_restr fset0 n.
proof. by apply fsetP => x;rewrite /restr in_fsetI in_fset0. qed.

lemma restr_0 s : restr s 0 = fset0.
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  by apply fsetP=> x; rewrite /restr in_fsetI in_fset0 mem_oflist mem_iota /#.
qed.

axiom N_pos : 0 <= N.

import RField StdOrder.RealOrder.

lemma Pr_PIR_s i0 &m x :
  Pr[PIR.main(i0) @ &m : oflist PIR.s = x] =
    if is_restr x N then 1%r/2%r^N else 0%r.
proof.
      (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
      have N_ge0 := N_pos.
      have Hll : Pr[PIR.main(i0) @ &m : true] = 1%r.
      + byphoare => //; proc; inline *; wp; while true (N-j); auto; smt(dbool_ll).
      have Hvalid : hoare [PIR.main : true ==> is_restr (oflist PIR.s) N].
      + proc; inline *; wp; sp.
        while (0 <= j <= N /\ is_restr (oflist PIR.s) j); auto;
          smt(is_restr_fset0 is_restr_addS is_restrS oflist_cons N_pos).
      case (is_restr x N) => [hx | hnx]; last first.
      (* Case: !is_restr x N => Pr = 0 *)
      + have : Pr[PIR.main(i0) @ &m : oflist PIR.s = x] <= 0%r.
        + byphoare (_ : true ==> _) => //; hoare; conseq Hvalid => /> /#.
        smt(mu_bounded).
      (* Case: is_restr x N => Pr = 1/2^N *)
      (* Prove uniformity: all valid subsets have same probability *)
      have Hunif: forall y, is_restr y N =>
        Pr[PIR.main(i0) @ &m : oflist PIR.s = y] =
        Pr[PIR.main(i0) @ &m : oflist PIR.s = x].
      + move=> y hy.
        byequiv (: ={arg, glob PIR} ==> (oflist PIR.s{1} = y) = (oflist PIR.s{2} = x)) => //;
          last smt().
        proc; inline *; wp.
        (* Membership-based invariant: for each processed index k,
           "k in s1 iff k in y" has same truth value as "k in s2 iff k in x" *)
        while (={j, i} /\
          (forall k, 0 <= k < j{1} =>
            ((k \in oflist PIR.s{1}) = (k \in y)) = ((k \in oflist PIR.s{2}) = (k \in x))) /\
          (forall k, k \in oflist PIR.s{1} => 0 <= k < j{1}) /\
          (forall k, k \in oflist PIR.s{2} => 0 <= k < j{2}) /\
          0 <= j{1} <= N).
        - wp; rnd (fun b => if (j{1} \in y) = (j{1} \in x) then b else !b).
          skip => /> &1 &2; smt(mem_oflist).
        - auto => />; split; first smt(mem_oflist).
          move=> sL jL sR jR hjL hjR.
          rewrite /is_restr /restr in hy.
          rewrite /is_restr /restr in hx.
          move=> *; rewrite eq_iff; split => heq;
            (apply fsetP => k;
             have /fsetP /(_ k) := hy; have /fsetP /(_ k) := hx;
             rewrite !in_fsetI !mem_oflist !mem_iota;
             smt(mem_oflist)).
      admit.
qed.

lemma Pr_PIR_s' i0 &m x :
  Pr[PIR.main(i0) @ &m : oflist PIR.s' = x] =
    if is_restr x N then 1%r/2%r^N else 0%r.
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  (* Symmetric to Pr_PIR_s — the s' distribution is identical *)
  rewrite -(Pr_PIR_s i0 &m x).
  byequiv (: ={arg, glob PIR} ==> PIR.s'{1} = PIR.s{2}) => //.
  proc; inline *; wp.
  while (={j, i} /\ PIR.s'{1} = PIR.s{2}).
  - wp; rnd (fun b => if (j{1} = i{1}) then !b else b); skip => /> /#.
  - auto.
qed.

lemma PIR_secuity_s_bypr i1 i2 &m1 &m2 x:
   Pr[PIR.main(i1) @ &m1 : oflist PIR.s = x] = Pr[PIR.main(i2) @ &m2 : oflist PIR.s = x].
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  by rewrite (Pr_PIR_s i1 &m1 x) (Pr_PIR_s i2 &m2 x).
qed.

lemma PIR_secuity_s'_bypr i1 i2 &m1 &m2 x:
   Pr[PIR.main(i1) @ &m1 : oflist PIR.s' = x] = Pr[PIR.main(i2) @ &m2 : oflist PIR.s' = x].
proof. (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  by rewrite (Pr_PIR_s' i1 &m1 x) (Pr_PIR_s' i2 &m2 x).
qed.    


(* Other version without explicite computation of the probability,
   we first show that the probability is uniform,
   unfortunatly this does not allows to conclude in easycrypt.
   We need to be able to do the projection of memories.
   So we need functions on memory
*)

lemma PIR_s_uniform (x1 x2 : int fset):
  0 <= N =>
  is_restr x1 N =>
  is_restr x2 N =>
  equiv [PIR.main ~ PIR.main : ={i} ==> (oflist PIR.s{1} = x1) = (oflist PIR.s{2} = x2)].
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  move=> hN hx1 hx2.
  bypr (oflist PIR.s{1} = x1) (oflist PIR.s{2} = x2); first smt().
  move=> &1 &2 [] _.
  + have -> : Pr[PIR.main(arg{1}) @ &1 : (oflist PIR.s = x1) = true] =
              Pr[PIR.main(arg{1}) @ &1 : oflist PIR.s = x1].
      byequiv (: ={arg, glob PIR} ==> ={PIR.s}) => //; first by sim. smt().
    have -> : Pr[PIR.main(arg{2}) @ &2 : (oflist PIR.s = x2) = true] =
              Pr[PIR.main(arg{2}) @ &2 : oflist PIR.s = x2].
      byequiv (: ={arg, glob PIR} ==> ={PIR.s}) => //; first by sim. smt().
    rewrite !Pr_PIR_s; smt().
  have -> : Pr[PIR.main(arg{1}) @ &1 : (oflist PIR.s = x1) = false] =
            Pr[PIR.main(arg{1}) @ &1 : oflist PIR.s <> x1].
    byequiv (: ={arg, glob PIR} ==> ={PIR.s}) => //; first by sim. smt().
  have -> : Pr[PIR.main(arg{2}) @ &2 : (oflist PIR.s = x2) = false] =
            Pr[PIR.main(arg{2}) @ &2 : oflist PIR.s <> x2].
    byequiv (: ={arg, glob PIR} ==> ={PIR.s}) => //; first by sim. smt().
  rewrite Pr [mu_not] Pr [mu_not] !Pr_PIR_s.
  have ll1 : Pr[PIR.main(arg{1}) @ &1 : true] = 1%r.
    byphoare => //; proc; inline *; wp; while true (N-j); auto; smt(dbool_ll).
  have ll2 : Pr[PIR.main(arg{2}) @ &2 : true] = 1%r.
    byphoare => //; proc; inline *; wp; while true (N-j); auto; smt(dbool_ll).
  by rewrite ll1 ll2; smt().
qed.

lemma PIR_s'_uniform (x1 x2 : int fset):
  0 <= N =>
  is_restr x1 N =>
  is_restr x2 N =>
  equiv [PIR.main ~ PIR.main : ={i} ==> (oflist PIR.s'{1} = x1) = (oflist PIR.s'{2} = x2)].
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  move=> hN hx1 hx2.
  bypr (oflist PIR.s'{1} = x1) (oflist PIR.s'{2} = x2); first smt().
  move=> &1 &2 [] _.
  + have -> : Pr[PIR.main(arg{1}) @ &1 : (oflist PIR.s' = x1) = true] =
              Pr[PIR.main(arg{1}) @ &1 : oflist PIR.s' = x1].
      byequiv (: ={arg, glob PIR} ==> ={PIR.s'}) => //; first by sim. smt().
    have -> : Pr[PIR.main(arg{2}) @ &2 : (oflist PIR.s' = x2) = true] =
              Pr[PIR.main(arg{2}) @ &2 : oflist PIR.s' = x2].
      byequiv (: ={arg, glob PIR} ==> ={PIR.s'}) => //; first by sim. smt().
    rewrite !Pr_PIR_s'; smt().
  have -> : Pr[PIR.main(arg{1}) @ &1 : (oflist PIR.s' = x1) = false] =
            Pr[PIR.main(arg{1}) @ &1 : oflist PIR.s' <> x1].
    byequiv (: ={arg, glob PIR} ==> ={PIR.s'}) => //; first by sim. smt().
  have -> : Pr[PIR.main(arg{2}) @ &2 : (oflist PIR.s' = x2) = false] =
            Pr[PIR.main(arg{2}) @ &2 : oflist PIR.s' <> x2].
    byequiv (: ={arg, glob PIR} ==> ={PIR.s'}) => //; first by sim. smt().
  rewrite Pr [mu_not] Pr [mu_not] !Pr_PIR_s'.
  have ll1 : Pr[PIR.main(arg{1}) @ &1 : true] = 1%r.
    byphoare => //; proc; inline *; wp; while true (N-j); auto; smt(dbool_ll).
  have ll2 : Pr[PIR.main(arg{2}) @ &2 : true] = 1%r.
    byphoare => //; proc; inline *; wp; while true (N-j); auto; smt(dbool_ll).
  by rewrite ll1 ll2; smt().
qed.