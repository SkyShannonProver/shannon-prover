require import AllCore RealLub RealFLub RealExp Distr SDist.

require import AllCore Bool StdRing StdOrder RealLub.

require import Finite FinType List Binomial DBool.

require import Ring StdRing StdOrder StdBigop Discrete.

require import RealFun RealSeq RealSeries.

import RField RealOrder.

import IterOp Bigint Bigreal Bigreal.BRA.

import IntOrder RealOrder RField.

import Biased.

op scale_rset (E: real -> bool) c x =
  exists x0, E x0 /\ c * x0 = x.

op is_fub (f: 'a -> real) r = forall x, f x <= r.

op has_fub (f: 'a -> real) = exists r, is_fub f r.

lemma has_fub_lub (f: 'a -> real) :
  has_fub f <=> has_lub (fun r => exists a, f a = r).

proof.

split.

- move => [r ub_r]; split; first (exists (f witness) => /#).

exists r => /#.

- move => has_lub_imgf; exists (flub f) => ?.

apply lub_upper_bound => /#.

qed.

lemma flub_upper_bound (F : 'a -> real) x :
    has_fub F => F x <= flub F.

proof.

move => H; rewrite has_fub_lub in H.

apply lub_upper_bound => /#.

qed.

lemma flub_le_ub (F : 'a -> real) r :
    is_fub F r => flub F <= r.

proof.

move => H.

have ub_r : ub (fun (x : real) => exists (a : 'a), F a = x) r.

move => y [a] <-; exact H.

apply lub_le_ub => //.

split; [by exists (F witness) witness| by exists r].

qed.

op p_max (p: 'a distr) = flub (mu1 p).

op min_entropy (p: 'a distr) = -log2 (p_max p).

lemma ge0_pmax (p: 'a distr) :
  0%r <= p_max p.

proof.

suff: mu1 p witness <= p_max p by smt(ge0_mu).

apply (@flub_upper_bound (mu1 p)); smt(le1_mu).

qed.

lemma le1_pmax (p: 'a distr) :
  p_max p <= 1%r.

proof.

by rewrite flub_le_ub.

qed.

lemma uni_dcond (d: 'a distr) P :
  is_uniform d =>
  is_uniform (dcond d P).

proof.

move => uni_d x y supp_x supp_y.

rewrite dcond_supp in supp_x.

case supp_x => [supp_x px].

rewrite dcond_supp in supp_y.

case supp_y => [supp_y py].

by rewrite !dcond1E => /#.

qed.

lemma mu_eq_l (d2 d1 : 'a distr) p : d1 = d2 => mu d1 p = mu d2 p by smt().

lemma dletEunit (d : 'a distr) F : F == dunit => dlet d F = d by smt(dlet_d_unit).

lemma dletEconst (d2 : 'b distr) (d1 : 'a distr) (F : 'a -> 'b distr) :
  is_lossless d1 =>
  (forall x, F x = d2) => dlet d1 F = d2.

proof.

move => d1_ll F_const; apply/eq_distr => b; rewrite dletE.

rewrite (eq_sum _ (fun x : 'a => mu1 d1 x * mu1 d2 b)) 1:/#.

by rewrite sumZr -weightE d1_ll.

qed.

lemma dmap_dcond (d : 'a distr) (f : 'a -> 'b) (p : 'b -> bool) :
  dmap (dcond d (p \o f)) f = dcond (dmap d f) p.

proof.

apply/eq_distr => y.

rewrite dmap1E dcond1E dcondE !dmapE.

case (p y) => [py|npy]; last by rewrite mu0_false // /#.

by congr; apply mu_eq; smt().

qed.

lemma eq_dcond (d : 'a distr) (p q : 'a -> bool) :
  (forall x, x \in d => p x = q x) => dcond d p = dcond d q.

proof.

move => eq_p_q; apply/eq_distr => x; rewrite !dcond1E.

case (x \in d) => [xd|xnd]; last by rewrite !(mu0_false _ (pred1 x)) /#.

by rewrite eq_p_q // (mu_eq_support _ _ _ eq_p_q).

qed.
