







require import AllCore RealLub RealFLub RealExp Distr SDist.
require import AllCore Bool StdRing StdOrder RealLub.
require import Finite FinType List Binomial DBool.
require import Ring StdRing StdOrder StdBigop Discrete.
require import RealFun RealSeq RealSeries.
  import RField RealOrder.
  import IterOp Bigint Bigreal Bigreal.BRA.
  import IntOrder RealOrder RField.
  import Biased.

lemma predIpp (p: 'a -> bool) :
  predI p p = p.
proof.
by apply/fun_ext=> x; rewrite /predI; case (p x) => //. qed.

lemma predUpp (p: 'a -> bool) :
  predU p p = p.
proof.
by apply/fun_ext=> x; rewrite /predU; case (p x) => //. qed.

lemma lub1 c :
  lub (fun x => x = c) = c.
proof.
apply eqr_le; split => [|_].
- apply lub_le_ub; smt().
- apply lub_upper_bound; smt().
qed.

op scale_rset (E: real -> bool) c x =
  exists x0, E x0 /\ c * x0 = x.

lemma has_lub_scale E c :
  c > 0%r =>
  has_lub E =>
  has_lub (scale_rset E c).
proof.
move => gt0_c has_lubE; split; 1: smt().
exists (c * lub E) => cx; smt(lub_upper_bound).
qed.

lemma lub_scale0 E :
  nonempty E =>
  lub (scale_rset E 0%r) = 0%r.
proof. smt(lub1). qed.

lemma lub_scaleE E c :
  has_lub E =>
  c >= 0%r =>
  lub (scale_rset E c) = c * lub E.
proof.
move => has_lubE ge0_c; case (c > 0%r) => [gt0_c|]; last by smt(lub_scale0).
apply eqr_le; split => [|_].
- apply lub_le_ub; first by apply has_lub_scale.
  smt(lub_upper_bound).
- rewrite -ler_pdivl_mull //.
  apply lub_le_ub => // x Ex.
  rewrite ler_pdivl_mull //.
  smt(lub_upper_bound has_lub_scale).
qed.

lemma log_le1 b x :
  b >= 1%r => 0%r < x <= 1%r => log b x <= 0%r.
proof.
rewrite /log => ge1_b bound_x.
case (ln b = 0%r); first (move => -> /#).
smt(lnV ln_ge0).
qed.

lemma le0_log b x :
  x <= 0%r => log b x = 0%r.
proof.
move => le0_x; suff: (ln x = 0%r) by smt().
exact ln_le0.
qed.




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
lemma flub_le (f g: 'a -> real) :
  has_fub g =>
  (forall x, f x <= g x) => flub f <= flub g.
proof.
move => [ym is_ub_ym] le_fg; rewrite ler_lub //=; 1: smt(); 2: exists (f witness) => /#.
split; first exists (g witness) => /#.
exists ym; smt(has_fub_lub).
qed.

lemma flub_scale (f: 'a -> real) c :
  has_fub f =>
  c >= 0%r =>
  flub (fun x => c * f x) = c * flub f.
proof.
move => H ge0_c; rewrite -lub_scaleE => //.
rewrite has_fub_lub in H => //.
apply eq_lub => /#.
qed.
lemma flub_const c :
  flub (fun _ : 'a => c) = c.
proof.
apply eqr_le; split; first apply flub_le_ub => /#.
move => _; apply (@flub_upper_bound (fun _ => c) witness) => /#.
qed.

lemma has_fub_leq (f g: 'a -> real) :
  has_fub g =>
  (forall x, f x <= g x) =>
  has_fub f.
proof. move => [??] /#. qed.
lemma has_fub_scale (f: 'a -> real) c:
  has_fub f =>
  c >= 0%r =>
  has_fub (fun x => c * f x).
proof. move => [ym ub_ym] ge0_c; exists (c * ym) => /#. qed.

lemma has_fub_mu1 (d: 'a distr) :
  has_fub (mu1 d).
proof.
apply (@has_fub_leq _ (fun _ => 1%r)) => // /#.
qed.





op min_entropy (p: 'a distr) = -log2 (p_max p).

lemma ge0_pmax (p: 'a distr) :
  0%r <= p_max p.
proof.
suff: mu1 p witness <= p_max p by smt(ge0_mu).
apply (@flub_upper_bound (mu1 p)); smt(le1_mu).
qed.
lemma gt0_pmax (p: 'a distr) x :
  x \in p => 0%r < p_max p.
proof.
move => in_xp; suff: p_max p >= mu1 p x by smt(ge0_mu).
apply (@flub_upper_bound (mu1 p)); smt(le1_mu).
qed.

lemma le1_pmax (p: 'a distr) :
  p_max p <= 1%r.
proof. by rewrite flub_le_ub. qed.
lemma ge0_me (p: 'a distr) :
  min_entropy p >= 0%r.
proof.
suff: log2 (p_max p) <= 0%r by smt().
case (p_max p > 0%r) => [gt0_p|]; 2: smt(le0_log).
apply log_le1 => //=; smt(le1_pmax).
qed.

lemma me_boundE alpha (d: 'a distr) x :
  x \in d =>
  min_entropy d >= alpha <=> p_max d <= 2%r ^ (-alpha).
proof.
move => in_xd.
have ->: (p_max d <= 2%r ^ -alpha) <=>
         (log2 (p_max d) <= log2 (2%r ^ -alpha))
  by smt(log_mono gt0_pmax exp_gt0).
have ->: log2 (2%r ^ -alpha) = -alpha by apply logK.
smt().
qed.

lemma uniform_pmax (d: 'a distr) :
  is_uniform d =>
  p_max d = weight d / (size (to_seq (support d)))%r.
proof.
move => unif_d; apply eqr_le; split.
- apply flub_le_ub => /= x.
  rewrite mu1_uni //.
  case (x \in d) => _; first by trivial.
  apply divr_ge0; first exact ge0_weight.
  smt(size_ge0).
- move => _; case (weight d = 0%r) => ?; first by smt(ge0_pmax).
  have [x in_xd]: exists x, x \in d by smt(witness_support ge0_mu).
  have <-: mu1 d x = weight d / (size (to_seq (support d)))%r by smt(mu1_uni).
  apply (@flub_upper_bound (mu1 d)) => /=; smt(le1_mu).
qed.

lemma dnull_pmax ['a] :
  p_max dnull<:'a> = 0%r.
proof.
rewrite /p_max.
have ->: (mu1 dnull<:'a>) = fun _ => 0%r by smt(dnull1E).
exact flub_const.
qed.

lemma dunit_pmax (x: 'a) :
  p_max (dunit x) = 1%r.
proof.
apply eqr_le; split => [|_]; first apply flub_le_ub => x'; by apply le1_mu.
have @/b2r /= <- := dunit1E x x.
apply (@flub_upper_bound (mu1 (dunit x))); smt(le1_mu).
qed.

lemma dunit_me (x: 'a) :
  min_entropy (dunit x) = 0%r.
proof. smt(ln_eq0 dunit_pmax). qed.

lemma dcond_pmax (d: 'a distr) P :
  p_max (dcond d P) <= p_max d / mu d P.
proof.
rewrite /p_max.
have ->: (fun x => mu1 (dcond d P) x) =
         (fun x => if P x then mu1 d x / mu d P else 0%r).
  by apply fun_ext; apply dcond1E.
rewrite -(@flub_scale (mu1 d) (inv (mu d P))) //=; first smt(le1_mu).
- apply invr_ge0; by apply ge0_mu.
apply flub_le => /= [|x].
- rewrite (@has_fub_scale (mu1 d) (inv (mu d P))) => //; first by apply has_fub_mu1.
  apply invr_ge0; by apply ge0_mu.
case (P x) => [|_]; first smt(ge0_mu).
rewrite (@mulr_ge0 (mu1 d x) (inv (mu d P))) ?ge0_mu //.
apply invr_ge0; by apply ge0_mu.
qed.

lemma dcond_me (d: 'a distr) P :
  mu d P > 0%r =>
  min_entropy (dcond d P) >= -log2 (p_max d) + log2 (mu d P).
proof.
move => dcond_valid.
have [x x_supp]: exists x, x \in dcond d P by smt(witness_support dcond_supp).
have H: p_max (dcond d P) <= p_max d / mu d P by apply dcond_pmax.
rewrite -(@log_mono 2%r) in H => //=; first smt(gt0_pmax).
- apply divr_gt0 => //; first smt(dcond_supp gt0_pmax).
rewrite logM in H; first smt(dcond_supp gt0_pmax).
- smt(dcond_supp gt0_pmax).
suff: log 2%r (inv (mu d P)) = -log 2%r (mu d P); smt(lnV ge0_mu).
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

lemma pmax_upper_bound (d: 'a distr) (x: 'a) :
  mu1 d x <= p_max d.
proof.
apply (flub_upper_bound (mu1 d) x); exists 1%r => /=.
by move => ?; apply le1_mu.
qed.

lemma dmap_dbiased (d: 'a distr) (p: 'a -> bool) :
  is_lossless d =>
  dmap d p = dbiased (mu d p).
proof.
move => d_ll; apply eq_distr => x.
rewrite dbiased1E clamp_id; first by smt(ge0_mu le1_mu).
rewrite dmap1E /(\o) /pred1; smt(mu_not).
qed.

lemma marginal_sampling_pred (d : 'a distr) (p : 'a -> bool) :
  is_lossless d =>
  d = dlet (dbiased (mu d p)) (fun b => if b then (dcond d p) else (dcond d (predC p))).
proof.
move => ?.
rewrite -dmap_dbiased => //.
rewrite {1} (marginal_sampling d p).
congr; apply fun_ext => b.
by case b => _; congr => /#.
qed.

lemma dbiased_true : dbiased 1%r = dunit true.
proof.
rewrite eq_distr => b.
by rewrite dbiased1E dunit1E /#.
qed.



lemma dprodEl (da : 'a distr) (db : 'b distr) Pa :
  mu (da `*` db) (fun (ab : 'a * 'b) => Pa ab.`1) = mu da Pa * weight db.
proof.
rewrite (mu_eq _ _ (fun (ab : 'a * 'b) => Pa ab.`1 /\ predT ab.`2)) 1:/#.
by rewrite dprodE.
qed.

lemma dprodEr (da : 'a distr) (db : 'b distr) Pb :
  mu (da `*` db) (fun (ab : 'a * 'b) => Pb ab.`2) = mu db Pb * weight da.
proof.
rewrite (mu_eq _ _ (fun (ab : 'a * 'b) => predT ab.`1 /\ Pb ab.`2)) 1:/#.
by rewrite dprodE RField.mulrC.
qed.

lemma le_dprod_or (da : 'a distr) (db : 'b distr) Pa Pb :
   mu (da `*` db) (fun (ab : 'a * 'b) => Pa ab.`1 \/ Pb ab.`2) <=
   mu da Pa * weight db + mu db Pb * weight da.
proof.
rewrite (mu_eq _ _ (predU (fun (p : 'a * 'b) => Pa p.`1)
                          (fun (p : 'a * 'b) => Pb p.`2))) 1:/#.
by rewrite mu_or dprodEl dprodEr; smt(mu_bounded).
qed.

lemma le_djoin_size (ds : 'a distr list) (x : 'a) r:
  (forall d y, d \in ds => mu1 d y <= r) =>
  mu (djoin ds) (fun s : 'a list => x \in s) <= (size ds)%r * r.
proof.
elim: ds => [|d ds IHds bound_ds]; first by rewrite djoin_nil dunitE.
rewrite djoin_cons /= dmapE /(\o).
rewrite (mu_eq _ _ (fun (p : 'a * 'a list) => p.`1 = x \/ x \in p.`2)).
- by case => y ys /= @/predU /#.
have E := le_dprod_or d (djoin ds) (pred1 x) (fun xs : 'a list => x \in xs).
apply (ler_trans _ _ _ E) => {E}.
apply (ler_trans (mu1 d x + mu (djoin ds) (fun (xs : 'a list) => x \in xs))).
  apply ler_add; apply ler_pimulr; smt(mu_bounded).
rewrite fromintD RField.mulrDl /=; apply ler_add; first by apply bound_ds.
by apply IHds => /#.
qed.

lemma sdist_dbiased a b :
  sdist (dbiased a) (dbiased b) = `|clamp a - clamp b|.
proof.
rewrite sdist_tvd !dbiased_ll /= normr0 /=.
rewrite (sumE_fin _ [true; false]) // /=; 1: smt().
rewrite !big_cons big_nil /predT /=; smt(dbiased1E).
qed.


lemma dexpand (d1 d2 : 'a distr) :
  d1 = dlet (dunit true) (fun b => if b then d1 else d2).
proof. by rewrite dlet_unit. qed.

lemma sdist_dcond (d : 'a distr) p :
  is_lossless d =>
  sdist d (dcond d p) <= mu d (predC p).
proof.
move => ?.
rewrite (dexpand (dcond _ _) (dcond d (predC p))) -dbiased_true.
rewrite {1} (marginal_sampling_pred d p) //.
apply (ler_trans (sdist (dbiased (mu d p)) (dbiased 1%r))).
- exact sdist_dlet.
by rewrite sdist_dbiased; smt(mu_not le1_mu).
qed.


lemma gt0_prodr_seq (P : 'a -> bool) (F : 'a -> real) (s : 'a list) :
  (forall (a : 'a), a \in s => P a => 0%r <= F a) =>
  0%r < BRM.big P F s =>
  (forall (a : 'a), a \in s => P a => 0%r < F a).
proof.
elim: s => // x s IHs F_ge0; rewrite BRM.big_cons.
have {IHs} IHs := IHs _; first by smt().
case: (P x) => [Px F_big_gt0 a [->|a_s] Pa | nPx /IHs]; smt().
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


lemma fin_muE (d : 'a distr) (E : 'a -> bool) : is_finite (support d) =>
  mu d E = big E (mu1 d) (to_seq (support d)).
proof.
move => fin_d.
rewrite (mu_eq_support d _ (mem (filter E (to_seq (support d))))).
- by move => x x_d; rewrite mem_filter mem_to_seq // x_d.
by rewrite mu_mem_uniq ?filter_uniq ?uniq_to_seq // big_filter.
qed.

lemma Jensen_fin_concave ['a] (d : 'a distr) f (g : real -> real) :
     is_finite (support d)
  => is_lossless d
  => (forall a b, convex (fun x => - g x) a b)
  => E d (g \o f) <= g (E d f).
proof.
move => d_fin d_ll g_concave.
have /= J := Jensen_fin d f (fun x => - g x) d_fin d_ll g_concave.
rewrite -ler_opp2; apply (@ler_trans _ _ _ J).
by rewrite -mulN1r -expZ lerr_eq &(eq_exp) => x x_d @/(\o) /=; rewrite mulN1r.
qed.

lemma E_fin (d : 'a distr) (f : 'a -> real) :
  is_finite (support d) => E d f = big predT (fun x => mu1 d x * f x) (to_seq (support d)).
proof.
move => fin_d.
rewrite /E (RealSeries.sumE_fin _ (to_seq (support d))) ?uniq_to_seq //.
- move => x /=. rewrite mem_to_seq //. smt(supportP).
by apply eq_bigr => /#.
qed.

lemma ler_mu_dcond (d : 'a distr) (p : 'a -> bool) x :
  p x => mu1 d x <= mu1 (dcond d p) x.
proof.
move => p_x; rewrite dcond1E p_x /=.
case (x \in d) => [x_d|]; last by move/supportPn => -> /#.
suff: 0%r < mu d p by smt(mu_bounded).
by apply/witness_support; exists x.
qed.

lemma finite_dcond (d : 'a distr) (p : 'a -> bool) :
  is_finite (support d) => is_finite (support (dcond d p)).
proof. by apply finite_leq => x /dcond_supp. qed.

lemma dmap_dcond (d : 'a distr) (f : 'a -> 'b) (p : 'b -> bool) :
  dmap (dcond d (p \o f)) f = dcond (dmap d f) p.
proof.
apply/eq_distr => y. rewrite dmap1E dcond1E dcondE !dmapE.
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

