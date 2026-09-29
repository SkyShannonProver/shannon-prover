require import AllCore Distr List IntDiv StdOrder.
(* Harness navigation probe: addzA (standard library). *)
require import DistrExtras_port.

import RealOrder Finite.

require DParams ConcreteDRing.

require DRing DVect MLWE SelfTargetMSIS.

require SimplifiedScheme.

abstract theory AbstractDilithium.

clone import DParams as Params.

clone import DRing as DR with
  op n <= n,
  op q <= q
proof prime_q by exact prime_q
proof gt0_n by exact gt0_n.

clone import DVect as DV with
  theory DR <= DR,
  op HL.alpha <- 2*gamma2,
  op HL.d     <- d
proof
  HL.ge2_alpha,
  HL.alpha_halfq_le,
  HL.even_alpha,
  HL.alpha_almost_divides_q.

realize HL.ge2_alpha by smt(gamma2_bound).

realize HL.even_alpha by smt().

realize HL.alpha_halfq_le by smt(gamma2_bound).

realize HL.alpha_almost_divides_q by apply gamma2_div.

import DV.MatRq.

import DV.HL.

type M.

type SK = matrix * vector * vector * vector.

type PK = matrix * high2 list.

type commit_t = high list.

type challenge_t = Rq.

type response_t = vector * hint_t list.

type Sig = challenge_t * response_t.

module type Hash  = {
  proc get(x : high list * M) : challenge_t
}.

module Dilithium (H: Hash) = {
  proc keygen() : PK * SK = {
    var pk, sk;
    var mA, s1, s2,t, t1,t0;
    mA <$ dmatrix dRq k l;
    s1 <$ dvector (dRq_ Params.eta_) l;
    s2 <$ dvector (dRq_ Params.eta_) k;
    t  <- mA *^ s1 + s2;
    t1 <- base2highbitsV t;
    t0 <- base2lowbitsV t;
    pk <- (mA, t1);
    sk <- (mA, s1, s2, t0);
    return (pk, sk);
  }

  proc sign(sk: SK, m: M) : Sig = {
    var z : vector;
    var h : hint_t list;
    var response : response_t option;
    var c : R <- witness;
    var ctr : int;
    var y, w, w1;
    var mA, s1, s2;
    var t0;

    (mA, s1, s2, t0) <- sk;

    response <- None;
    while(response = None) {
      y <$ dvector (dRq_ (gamma1 - 1)) l;
      w <- mA *^ y;
      w1 <- highBitsV w;
      c <@ H.get((w1, m));
      z <- y + c ** s1;
      if(inf_normv z < gamma1 - beta_ /\
         inf_normv (lowBitsV (mA *^ y - c ** s2)) < gamma2 - beta_) {
        h <- makeHintV (- c ** t0) (w - c ** s2 + c ** t0);
        response <- Some(z,h);
      }
    }
    return (c, oget response);
  }

  proc verify(pk: PK, m : M, sig : Sig) = {
    var w1, c;
    var response;
    var z, h;
    var c';
    var mA, t1;
    (mA, t1) <- pk;

    (c, response) <- sig;
    (z, h) <- response;
    w1 <- useHintV h (mA *^ z - c ** base2shiftV t1);
    c' <@ H.get((w1, m));
    return size z = l /\ size h = k /\ inf_normv z < gamma1 - beta_ /\ c = c';
  }
}.

const qS : { int | 0 <= qS } as qS_ge0.

const qH : { int | 0 <= qH } as qH_ge0.

op dA = dmatrix dRq k l.

op dy = dvector (dRq_ (gamma1 - 1)) l.

op dz = dvector (dRq_ (gamma1 - beta_ - 1)) l.

op check_mx : matrix -> bool.

axiom check_valid A : check_mx A => A \in dA.

op A0 : { matrix | check_mx A0 } as A0P.

const delta_ : { real | 0%r <= delta_ }  as delta_gt0.

axiom check_mx_most : mu dA (predC check_mx) <= delta_.

const eps_comm  : { real | 0%r < eps_comm } as eps_comm_gt0.

axiom check_mx_entropy :
  E (dcond dA check_mx) (fun mA =>
    p_max (dmap dy (fun y => highBitsV (mA *^ y)))) <= eps_comm.

const eps_low : { real | eps_low < 1%r } as eps_low_lt1.

axiom bound_low c (t : vector) (mA : matrix) :
  c \in dC tau => t \in dvector dRq k => check_mx mA =>
  mu dz (fun z => gamma2 - beta_ <= inf_normv (lowBitsV (mA *^ z - c ** t)) ) <= eps_low.

clone import DigitalSignaturesRO as DSS with
type DS.pk_t <- PK,
type DS.sk_t <- SK,
type DS.msg_t <- M,
type DS.sig_t <- Sig,
type PRO.in_t <= commit_t*M,
type PRO.out_t <= challenge_t,
op   PRO.dout <= fun _ => dC tau,
op   EFCMA.q_efcma <= qS
proof* by smt(qS_ge0).

import DSS.DS.Stateless.

module H = DSS.PRO.RO.

clone SimplifiedScheme as SD with
  theory DR <- DR,
  theory DV <- DV,
  type M <- M,

  theory Params <- Params,

  op check_mx <- check_mx,
  op eps_comm <- eps_comm,
  op eps_check <- delta_,
  op eps_low <- eps_low,
  axiom eps_comm_gt0 <- eps_comm_gt0,
  axiom eps_check_gt0 <- delta_gt0,
  axiom check_mx_entropy <- check_mx_entropy,
  axiom bound_low <- bound_low,
  axiom eps_low_lt1 <- eps_low_lt1,
  axiom check_mx_most <- check_mx_most,
  axiom check_valid <- check_valid,

  op A0 <- A0,
  axiom A0P <- A0P,

  op qS <- qS,
  op qH <- qH,
  axiom qS_ge0 <- qS_ge0,
  axiom qH_ge0 <- qH_ge0
proof* by smt(gt0_eta gt0_k gt0_l gamma2_bound gamma2_div gt0_beta beta_gamma1_lt beta_gamma2_lt gt0_d tau_bound eta_tau_leq_b ub_d).


type SK' = matrix * vector * vector.

type PK' = matrix * vector.

module (RedS (A : Adv_EFCMA_RO) : SD.FSaCR.DSS.Adv_EFCMA_RO)
       (H : Hash) (O : SOracle_CMA) = {
 proc forge (pk: PK') = {
    var r,mA,t,t1;
    (mA,t) <- pk;
    t1 <- base2highbitsV t;
    r <@ A(H,O).forge(mA,t1);
    return r;
  }
}.

module MLWE_L (A : SD.RqMLWE.Adversary) = SD.RqMLWE.GameL(A).

module MLWE_R (A : SD.RqMLWE.Adversary) = SD.RqMLWE.GameR(A).

module SelfTargetMSIS (A : SD.RqStMSIS.Adversary) = SD.RqStMSIS.Game(A).

module RedMLWE (A : Adv_EFCMA_RO) =
  SD.RedMLWE(SD.RedCR(SD.CMAtoKOA.RedKOA(SD.CG.RedFSaG(RedS(A)), SD.HVZK_Sim_Inst)),
  SD.FSaCR.DSS.PRO.RO).

module RedStMSIS (A : Adv_EFCMA_RO) =
  SD.RedMSIS(SD.RedCR(SD.CMAtoKOA.RedKOA(SD.CG.RedFSaG(RedS(A)), SD.HVZK_Sim_Inst))).

section PROOF.

declare module A <: Adv_EFCMA_RO{
  -H, -O_CMA_Default,
  -SD.H,
  -SD.G,
  -SD.OpBasedSig,
  -SD.CMAtoKOA.ORedKOA,
  -SD.CMAtoKOA.CountS,
  -SD.CMAtoKOA.CountH,
  -SD.CountS,
  -SD.CountH,
  -SD.O_CMA_Default_G,
  -SD.RO_G,
  -SD.OpBasedSigG,
  -RedS,
  -SD.FSaCR.DSS.DS.Stateless.O_CMA_Default
}.
declare axiom A_ll (SO' <: SOracle_CMA{-A}) (H' <: Hash{-A} ) :
  islossless SO'.sign => islossless H'.get => islossless A(H', SO').forge.
declare axiom A_bound
  (H' <: Hash{-SD.CountS, -SD.CountH, -A} )
  (SO' <: SOracle_CMA{-SD.CountS, -SD.CountH, -A} ) :
  hoare[ A(SD.CountH(H'), SD.CountS(SO')).forge :
      SD.CountH.qh = 0 /\ SD.CountS.qs = 0 ==>
      SD.CountH.qh <= qH /\ SD.CountS.qs <= qS].
op p0 = (size (to_seq (support dz)))%r / (size (to_seq (support dy)))%r.
op p_rej : real = (p0 * eps_low) + (1.0 - p0).

  (* SCRATCHPAD BEGIN — your own declarations may go below this line *)

lemma rejection_parameter : p_rej = SD.p_rej.
proof. by rewrite /p_rej /p0 /SD.p_rej /SD.line12_magic_number /SD.dsimz /DR.dRq_open. qed.

lemma rejection_range : 0%r <= p_rej < 1%r.
proof. by rewrite rejection_parameter; exact SD.p_rej_bounded. qed.

lemma simplify_scheme &m :
 Pr[EF_CMA_RO(Dilithium, A, H, O_CMA_Default).main() @ &m : res] =
 Pr[SD.FSaCR.DSS.EF_CMA_RO(SD.DilithiumS, RedS(A), SD.H,
      SD.FSaCR.DSS.DS.Stateless.O_CMA_Default).main() @ &m : res].
proof.
(* COMPLETE THIS *)
  byequiv (_ : ={glob A} ==> ={res}) => //.
  proc.
  inline DSS.EFCMA.EF_CMA SD.FSaCR.DSS.EFCMA.EF_CMA.
  inline *.
  wp.
  rnd; wp.
  call (_ : PRO.RO.m{1} = SD.FSaCR.DSS.PRO.RO.m{2} /\ O_CMA_Default.qs{1} = SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.qs{2} /\ O_CMA_Default.sk{1} = (SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}.`1, SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}.`2, SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}.`3, base2lowbitsV (SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}.`1 *^ SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}.`2 + SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}.`3))).
  proc; inline *; wp.
  while (={m, m0, c, response, mA, s1, s2, t0} /\ PRO.RO.m{1} = SD.FSaCR.DSS.PRO.RO.m{2} /\ O_CMA_Default.qs{1} = SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.qs{2} /\ O_CMA_Default.sk{1} = (SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}.`1, SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}.`2, SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}.`3, base2lowbitsV (SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}.`1 *^ SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}.`2 + SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}.`3))).
  by auto.
  by auto.
  by proc; auto.
  by auto.
qed.

lemma norm_sub_bound (u v : vector) a b :
  size u = size v => 0 <= a => 0 <= b =>
  inf_normv u <= a => inf_normv v <= b => inf_normv (u-v) <= a+b.
proof.
  move=> suv ha hb hu hv.
  rewrite inf_normv_ler // in hu.
  rewrite inf_normv_ler // in hv.
  apply (inf_normv_ler _ (a+b)); first smt().
  move=> i hi.
  have hiu : 0 <= i < size u by smt(size_addv size_oppv).
  have hiv : 0 <= i < size v by smt().
  have h1 := hu i hiu.
  have h2 := hv i hiv.
  rewrite get_addv getvN.
  smt(cnorm_triangle cnormN).
qed.

lemma norm_cat_bound (u v : vector) b :
  0 <= b => inf_normv u <= b => inf_normv v <= b =>
  inf_normv (u || v) <= b.
proof.
  move=> hb hu hv.
  rewrite inf_normv_ler // in hu.
  rewrite inf_normv_ler // in hv.
  apply (inf_normv_ler _ b) => // i hi.
  rewrite get_catv; case (i < size u) => hc.
  - apply hu; smt(size_catv).
  - apply hv; smt(size_catv).
qed.

lemma shiftV_size w : size (shiftV w) = size w.
proof. by rewrite /shiftV size_oflist size_map. qed.

lemma hint_error_bound h r :
  size h = size r =>
  inf_normv (r - shiftV (useHintV h r)) <= 2*gamma2+1.
proof.
  move=> hs.
  apply (inf_normv_ler _ (2*gamma2+1)); first smt(gamma2_bound).
  move=> i hi.
  have hir : 0 <= i < size r by smt(size_addv size_oppv shiftV_size size_useHintV).
  rewrite get_addv getvN /shiftV (get_oflist witness).
  - by rewrite size_map size_useHintV; smt().
  rewrite (nth_map witness); first by rewrite size_useHintV; smt().
  rewrite /useHintV (nth_map (witness,witness)); first by rewrite size_zip size_tolist; smt().
  rewrite nth_zip; first by rewrite size_tolist; smt().
  rewrite /uncurry nth_tolist //.
  exact (hide_low2 r.[i] (nth witness h i)).
qed.

lemma shiftV_injective : injective shiftV.
proof.
  move=> x y hxy.
  have hmap : map shift x = map shift y by exact (oflist_inj _ _ hxy).
  exact (inj_map shift shift_inj x y hmap).
qed.

op lattice_witness (mA : matrix) (t : vector) (c : Rq) (z : vector) (h : hint_t list) =
  let r = mA *^ z - c ** base2shiftV (base2highbitsV t) in
  (c ** base2lowbitsV t - (r - shiftV (useHintV h r))) || z || vectc 1 c.

lemma lattice_witness_valid mA t c z h :
  size mA = (k,l) => size t = k => size z = l => size h = k =>
  c \in dC tau => inf_normv z < gamma1-beta_ =>
  let y = lattice_witness mA t c z h in
  inf_normv y <= max (gamma1-beta_) (tau * 2^(d-1) + (2*gamma2+1)) /\
  y.[k+(l+1)-1] = c /\
  (onem k || (mA || colmx (-t))) *^ y = shiftV (SD.recover (mA,t) c (z,h)).
proof.
(* COMPLETE THIS *)
  move=> hA ht hz hh hc hnorm.
  have [hc1 hc2] : cnorm c <= 1 /\ l1_norm c = tau by move: hc; rewrite supp_dC.
  pose r := mA *^ z - c ** base2shiftV (base2highbitsV t).
  have hr : size r = k.
  - rewrite /r size_addv size_oppv size_scalarv size_base2shiftV size_base2highbitsV size_mulmxv.
  have [hAr hAc] := hA.
  by rewrite ht hAr /max; smt().
  have he := hint_error_bound h r _; first by rewrite hh hr.
  have hs : size (r - shiftV (useHintV h r)) = k by rewrite size_addv size_oppv shiftV_size size_useHintV hh hr /min /max; smt().
  have hu : size (c ** base2lowbitsV t - (r - shiftV (useHintV h r))) = k by rewrite size_addv size_oppv size_scalarv size_base2lowbitsV ht hs /max; smt().
  have hp : 0 < 2 ^ (d-1) by apply IntOrder.expr_gt0.
  have hlow : inf_normv (c ** base2lowbitsV t) <= tau * 2 ^ (d-1) by apply l1_inf_norm_product_ub; smt(tau_bound b2low_bound).
  have hub : inf_normv (c ** base2lowbitsV t - (r - shiftV (useHintV h r))) <= tau * 2 ^ (d-1) + (2*gamma2+1).
  - apply norm_sub_bound; [by rewrite size_scalarv size_base2lowbitsV ht hs | smt(tau_bound) | smt(gamma2_bound) | exact hlow | exact he].
  have hcvec : inf_normv (vectc 1 c) <= 1.
  - rewrite inf_normv_ler // => i hi.
  rewrite get_vectc; first by move: hi; rewrite size_vectc /max; smt().
  exact hc1.
  rewrite /lattice_witness -/r /=.
  split.
  apply norm_cat_bound.
  rewrite /max.
  have hg : 0 < gamma1 - beta_ by have := beta_gamma1_lt; smt().
  move: hg.
  clear.
  smt().
  apply (IntOrder.ler_trans (tau * 2 ^ (d-1) + (2*gamma2+1))); first exact hub.
  exact IntOrder.maxrr.
  have hg : 1 <= gamma1-beta_ by have := beta_gamma1_lt; smt().
  have hm := IntOrder.maxrl (gamma1-beta_) (tau * 2^(d-1)+(2*gamma2+1)).
  apply norm_cat_bound; smt().
  split.
  - rewrite get_catv_r; first by rewrite hu; have := gt0_l; smt().
  rewrite hu get_catv_r; first by rewrite hz; smt().
  rewrite hz get_vectc; smt().
  have [hAr hAc] := hA.
  rewrite mulmxv_cat; first by rewrite hu /= /max; have := gt0_k; smt().
  rewrite mulmxv_cat; first by rewrite hAc hz.
  rewrite -{1}hu mulmx1v mul_colmxc scalarvN.
  rewrite /SD.recover /= -/r.
  apply eq_vectorP; split.
  - rewrite size_addv hu size_addv size_oppv size_scalarv size_mulmxv hAr ht shiftV_size size_useHintV hh hr /max /min; smt().
  move=> i hi.
  rewrite !get_addv !getvN /r !get_addv !getvN.
  rewrite -{1}[t]b2high_lowPv.
  rewrite b2high_lowPv.
  have hct : c ** t = c ** base2shiftV (base2highbitsV t) + c ** base2lowbitsV t by rewrite -scalarvDr b2high_lowPv.
  rewrite hct get_addv.
  ring.
qed.

section LATTICE.
declare module B <: SD.FSaCR.DSS.Adv_EFKOA_RO {-SD.H, -SD.G}.

lemma koa_mlwe_left &m :
 Pr[SD.FSaCR.DSS.EF_KOA_RO(SD.DilithiumS, B, SD.H).main() @ &m : res] =
 Pr[SD.RqMLWE.GameL(SD.RedMLWE(B, SD.H)).main() @ &m : res].
proof.
  byequiv (_ : ={glob B} ==> ={res}) => //.
  proc.
  inline *.
  sim.
  by auto.
qed.

end section LATTICE.

lemma operation_scheme &m :
 Pr[SD.FSaCR.DSS.EF_CMA_RO(SD.DilithiumS, RedS(A), SD.H,
      SD.FSaCR.DSS.DS.Stateless.O_CMA_Default).main() @ &m : res] =
 Pr[SD.FSaCR.DSS.EF_CMA_RO(SD.OpBasedSig, RedS(A), SD.H,
      SD.FSaCR.DSS.DS.Stateless.O_CMA_Default).main() @ &m : res].
proof.
(* COMPLETE THIS *)
  byequiv (_ : ={glob A} ==> ={res}) => //.
  proc.
  inline SD.FSaCR.DSS.EFCMA.EF_CMA.
  inline *.
  wp.
  rnd; wp.
  call (_ : ={SD.H.m, SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk,
               SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.qs}).
  proc; inline *; wp.
  while (={m, m0, sk, c, SD.H.m, SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk, SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.qs} /\ response{1} = oz{2} /\ sk{1} = (mA{1}, s1{1}, s2{1}) /\ t0{1} = base2lowbitsV (mA{1} *^ s1{1} + s2{1})).
  seq 1 2 : (={m, m0, sk, c, SD.H.m, SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk, SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.qs} /\ response{1} = None /\ oz{2} = None /\ sk{1} = (mA{1}, s1{1}, s2{1}) /\ t0{1} = base2lowbitsV (mA{1} *^ s1{1} + s2{1}) /\ w0{2} = highBitsV (mA{1} *^ y{1}) /\ SD.OpBased.P.pstate{2} = y{1}).
  rnd (fun y => (highBitsV (mA{1} *^ y), y)) (fun p => p.`2); wp; skip; progress.
  move: H; rewrite /SD.commit /= supp_dmap; smt().
  have Hp := H _ H0; rewrite /SD.commit /SD.dy /= dmap1E; apply mu_eq => y; rewrite /pred1 /(\o) /=.
  rewrite {1}Hp /=; apply eq_iff; split; first by move=> [_ ->].
  by move=> ->.
  rewrite /SD.commit /SD.dy /= supp_dmap; by exists yL.
  wp; rnd; wp; skip; progress; rewrite /SD.respond /=; smt().
  auto => />.
  move=> &2; by case: (SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{2}).
  proc; sim.
  seq 8 4 : (={pk, sk, glob A, SD.H.m}).
  rndsem*{1} 1.
  wp; rnd; wp; skip; rewrite /SD.keygen /SD.ds1 /SD.ds2 /=; auto.
  auto => />; rewrite /SD.recover /SD.verify /=.
  move=> &2 [msg [ch [zz hh]]] hm qs rr Hr; case: (pk{2}) => aa tt /=; smt().
qed.

op xr_ofreal (x : real) = Xreal.Rpbar.rp (Xreal.Rp.of_reald x).
op xr_guard (b : bool) (x : Xreal.Rpbar.xreal) = if b then x else Xreal.Rpbar.oo.

lemma expected_choice (d : 'a distr) (p : 'a -> bool) a b :
  is_lossless d => 0%r <= a => 0%r <= b =>
  Xreal.Ep d (fun x => if p x then xr_ofreal a else xr_ofreal b) =
  xr_ofreal (mu d p * a + (1%r-mu d p) * b).
proof.
(* COMPLETE THIS *)
  move=> hd ha hb.
  rewrite -(Xreal.Ep_dmap d p (fun v => if v then xr_ofreal a else xr_ofreal b)).
  rewrite (dmap_dbiased d p hd) Xreal.Ep_dbiased; first smt(mu_bounded).
  rewrite /xr_ofreal /=.
  have hm : 0%r <= mu d p by smt (ge0_mu).
  have hn : 0%r <= 1%r - mu d p by smt (le1_mu).
  have hma : 0%r <= mu d p * a by smt.
  have hnb : 0%r <= (1%r - mu d p) * b by smt.
  by rewrite (Xreal.Rp.of_realD _ _ hma hnb) (Xreal.Rp.of_realM _ _ hm ha) (Xreal.Rp.of_realM _ _ hn hb).
qed.

module Trials = {
  proc run(sk : SD.SK) = {
    var n, x, oz;
    n <- 0;
    oz <- None;
    while (oz = None) {
      x <$ SD.commit sk `*` dC tau;
      oz <- SD.respond sk x.`2 x.`1.`2;
      n <- n+1;
    }
    return n;
  }
}.

lemma trials_mean sk0 : SD.check sk0 =>
  ehoare [Trials.run : xr_guard (arg = sk0) (xr_ofreal (1%r/(1%r-p_rej))) ==> xr_ofreal res%r].
proof.
(* COMPLETE THIS *)
  move=> hsk; proc.
  while (xr_guard (sk = sk0 /\ 0 <= n)
    (xr_ofreal (n%r + if oz = None then 1%r/(1%r-p_rej) else 0%r))).
  - move=> &hr; apply Xreal.xle_cxr_r => ho.
  rewrite /xr_guard -/Xreal.(`|`).
  apply Xreal.xle_cxr_r => _.
  rewrite ifF // RField.addr0.
  - wp; skip.
  move=> &hr; apply Xreal.xle_cxr_r => hoz; rewrite /xr_guard; case (sk{hr} = sk0 /\ 0 <= n{hr}) => hpre /=.
  move: hpre => [hkey hn]; have hn1 : 0 <= n{hr} + 1 by smt(); rewrite hkey hn1 hoz /=.
  rewrite hkey hn1 hoz /=.
  have heq : (fun (x : (S.sT list * vector) * Rq) => xr_ofreal ((n{hr}+1)%r + if SD.respond sk0 x.`2 x.`1.`2 = None then inv (1%r-p_rej) else 0%r)) = (fun (x : (S.sT list * vector) * Rq) => if SD.respond sk0 x.`2 x.`1.`2 = None then xr_ofreal ((n{hr}+1)%r + inv (1%r-p_rej)) else xr_ofreal (n{hr}+1)%r) by apply fun_ext => x; case (SD.respond sk0 x.`2 x.`1.`2 = None) => //=.
  rewrite heq.
  have hd : is_lossless (SD.commit sk0 `*` dC tau).
  - rewrite dprod_ll SD.commit_ll /=; apply dC_ll.
  have ht := tau_bound.
  move: ht; clear; smt().
  clear heq hoz hkey hn1.
  have hp := rejection_range.
  have hi : 0%r <= inv (1%r-p_rej).
  - rewrite invr_ge0; move: hp; clear.
  move: p_rej => p; smt().
  rewrite expected_choice //.
  move: hn hi; clear; move: (inv (1%r-p_rej)) => r; smt().
  move: hn; clear; smt().
  have hq := SD.rej_bound sk0 hsk.
  rewrite -rejection_parameter in hq.
  apply Xreal.Rpbar.xle_rle.
  have hmu := mu_bounded (SD.commit sk0 `*` dC tau) (fun (x : (S.sT list * vector) * Rq) => SD.respond sk0 x.`2 x.`1.`2 = None).
  move: hn hp hi hq hmu; clear.
  move: (mu (SD.commit sk0 `*` dC tau) (fun (x : (S.sT list * vector) * Rq) => SD.respond sk0 x.`2 x.`1.`2 = None)) => q.
  move: p_rej => p.
  move=> hn hp hi hq hmu.
  have hne : 1%r-p <> 0%r by smt().
  have hv : (1%r-p) * inv (1%r-p) = 1%r by field; exact hne.
  smt().
  trivial.
  wp; skip; simplify.
  trivial.
qed.

lemma uniform_vector_negation :
  dmap (dvector dRq k) (fun v : vector => -v) = dvector dRq k.
proof.
  apply eq_distr => v.
  rewrite (dmap1E_can _ _ (fun v : vector => -v)); first by move=> x; rewrite oppvK.
  - by move=> x _ /=; rewrite ?oppvK.
  apply dvector_rnd_funi; last by rewrite size_oppv.
  by apply is_full_funiform; [exact dRq_fu | exact dRq_uni].
qed.

lemma uniform_matrix_extension :
  dmatrix dRq k (l+1) =
  dmap (dA `*` dvector dRq k)
       (fun mt : matrix * vector => mt.`1 || colmx (-mt.`2)).
proof.
  rewrite dmatrixSrr; [smt(gt0_k) | smt(gt0_l) |].
  rewrite -{1}uniform_vector_negation dmap_dprodR dmap_comp.
  done.
qed.

op hash_tables_match (hm : (high list * M, Rq) FMap.fmap)
                     (gm : (vector * M, Rq) FMap.fmap) =
  forall w msg, FMap."_.[_]" hm (w,msg) = FMap."_.[_]" gm (shiftV w,msg).

op hash_table_valid (hm : (high list * M, Rq) FMap.fmap) =
  forall x c, FMap."_.[_]" hm x = Some c => c \in dC tau.

lemma random_key_msis (C <: SD.FSaCR.DSS.Adv_EFKOA_RO {-SD.H, -SD.G}) &m :
 Pr[SD.RqMLWE.GameR(SD.RedMLWE(C,SD.H)).main() @ &m : res] <=
 Pr[SD.RqStMSIS.Game(SD.RedMSIS(C),SD.G).main() @ &m : res].
proof.
(* COMPLETE THIS *)
  byequiv (_ : ={glob C} ==> res{1} => res{2}) => //.
  proc.
  inline *.
  wp.
  rnd; wp.
  call (_ : hash_tables_match SD.H.m{1} SD.G.m{2} /\ hash_table_valid SD.H.m{1}).
  proc; inline *; auto.
  move=> &1 &2 [Hx [Hm Hv]]; rewrite Hx /=; move=> c Hc; rewrite Hc /=; rewrite /hash_tables_match in Hm; rewrite !FMap.domE -Hm; case: (FMap."_.[_]" SD.FSaCR.DSS.PRO.RO.m{1} (w1{2}, mu{2}) = None) => Hfresh /=.
  rewrite !FMap.get_set_sameE /= /hash_tables_match /hash_table_valid; split.
  move=> w msg; rewrite !FMap.get_setE -Hm; have He : (shiftV w = shiftV w1{2}) = (w = w1{2}) by smt(shiftV_injective); rewrite /= He.
  smt().
  move=> x0 c0; rewrite FMap.get_setE; move: Hv; rewrite /hash_table_valid; smt().
  by rewrite /hash_tables_match; split.
  wp; rndsem*{1} 0.
  rnd (fun mt : matrix * vector => mt.`1 || colmx (-mt.`2)) (fun mb : matrix => (subm mb 0 k 0 l, -col mb l)); wp; skip.
  rewrite /dmap -dprod_dlet; move=> &1 &2 HC; split.
  move=> mb Hb; have Hsize := size_dmatrix dRq k (l+1) mb Hb; have Hk : 0 <= k by smt(gt0_k); have Hl : 0 <= l by smt(gt0_l); move: (Hsize Hk _); first smt(); move=> [Hr Hcol]; rewrite /= oppvK -Hr; rewrite subm_colmx //; smt().
  have Hl : 0 <= l by smt(gt0_l).
  have Hl1 : 0 <= l+1 by smt().
  have [Hr Hcol] := Hsize Hk Hl1.
  rewrite /= oppvK -Hr subm_colmx //.
  move=> Hinv; split; first (move=> mb Hb; have Hk : 0 <= k by smt(gt0_k)).
  have Hl : 0 <= l by smt(gt0_l).
  have Hl1 : 0 <= l+1 by smt().
  have Hsize := size_dmatrix dRq k (l+1) mb Hb Hk Hl1.
  rewrite (dmatrixRSr1E dRq mb k l Hk Hl Hsize) !dprod1E.
  have Hneg : mu1 (dvector dRq k) (col mb l) = mu1 (dvector dRq k) (-col mb l).
  rewrite -{1}uniform_vector_negation.
  apply (dmap1E_can _ _ (fun v : vector => -v)); rewrite /cancel /=; smt(oppvK).
  by rewrite Hneg.
  move=> Hmu [ma t] Hmt /=.
  have Hsupp : (ma || colmx (-t)) \in dmatrix dRq k (l+1) by (rewrite uniform_matrix_extension supp_dmap; exists (ma,t); rewrite /dA /=).
  have Hk : 0 <= k by smt(gt0_k).
  have Hl : 0 <= l by smt(gt0_l).
  move: Hmt => /supp_dprod [Hma Ht].
  have [Hr Hcol] := size_dmatrix dRq k l ma Hma Hk Hl.
  have Hts := size_dvector dRq k t Ht.
  have Hsub : subm (ma || colmx (-t)) 0 k 0 l = ma by rewrite -Hr -Hcol subm_catmrCl.
  have Hlast : -col (ma || colmx (-t)) l = t.
  rewrite col_catmrR.
  rewrite Hr rows_colmx size_oppv Hts /max; smt().
  by rewrite Hcol.
  rewrite Hcol /=.
  by rewrite oppvK.
  rewrite Hsub Hlast /=.
  split; first exact Hsupp.
  move=> _.
  split.
  rewrite HC /hash_tables_match /hash_table_valid.
  simplify; split; first (move=> w msg; rewrite !FMap.emptyE).
  trivial.
  move=> x0 c1; rewrite FMap.emptyE; trivial.
  move=> _ [msg [c [z h]]] resultR CL ml CR mr [<- [HCR [Hm Hv]]] r0 Hr0.
  rewrite /= Hr0 /= -/(lattice_witness ma t c z h).
  pose y := (c ** base2lowbitsV t - (ma *^ z - c ** base2shiftV (base2highbitsV t) - shiftV (useHintV h (ma *^ z - c ** base2shiftV (base2highbitsV t)))) || z || vectc 1 c).
  pose w := useHintV h (ma *^ z - c ** base2shiftV (base2highbitsV t)).
  rewrite !FMap.get_set_sameE /=.
  have Htk : size t = k by (rewrite Hts /max; smt()).
  have HW := lattice_witness_valid ma t c z h.
  rewrite /lattice_witness -/y /SD.recover /= -/w in HW.
  rewrite /hash_tables_match in Hm.
  have Hlookup := Hm w msg.
  rewrite /hash_table_valid in Hv.
  have Hvalid := Hv (w,msg) c.
  rewrite !FMap.domE.
  case: (FMap."_.[_]" ml (w,msg) = None) => Hfresh; case: (FMap."_.[_]" mr ((onem k || (ma || colmx (-t))) *^ y,msg) = None) => Hright /=; move=> [Hz [Hh [Hnorm Hc]]].
  have Hcs : c \in dC tau by rewrite Hc.
  have Hsz : rows ma = k /\ cols ma = l by split.
  have [Hn [Hyc Hprod]] := HW Hsz Htk Hz Hh Hcs Hnorm.
  by rewrite Hn Hyc Hc.
  have Hcs : c \in dC tau by rewrite Hc.
  have Hsz : rows ma = k /\ cols ma = l by split.
  have [Hn [Hyc Hprod]] := HW Hsz Htk Hz Hh Hcs Hnorm.
  by move: Hright; rewrite Hprod -Hlookup Hfresh.
  have Hcs : c \in dC tau by (apply Hvalid; rewrite Hc some_oget).
  have Hsz : rows ma = k /\ cols ma = l by split.
  have [Hn [Hyc Hprod]] := HW Hsz Htk Hz Hh Hcs Hnorm.
  by move: Hright; rewrite Hprod -Hlookup; smt().
  have Hcs : c \in dC tau by (apply Hvalid; rewrite Hc some_oget).
  have Hsz : rows ma = k /\ cols ma = l by split.
  have [Hn [Hyc Hprod]] := HW Hsz Htk Hz Hh Hcs Hnorm.
  by rewrite Hn Hyc Hprod -Hlookup -Hc.
qed.

lemma koa_recovery (D <: SD.FSaG.DSS.Adv_EFKOA_RO {-SD.H, -SD.RO_G, -SD.OpBasedSigG}) &m :
 Pr[SD.EF_KOA_RO_G(SD.OpBasedSigG,D,SD.RO_G).main() @ &m : res] <=
 Pr[SD.FSaCR.DSS.EF_KOA_RO(SD.DilithiumS,SD.RedCR(D),SD.H).main() @ &m : res].
proof.
(* COMPLETE THIS *)
  byequiv (_ : ={glob D} ==> res{1} => res{2}) => //.
  proc.
  inline *.
  wp.
  rnd{2}; wp.
  rnd; wp.
  call (_ : SD.RO_G.m{1} = SD.H.m{2}).
  - by proc; auto.
  seq 4 8 : (={pk, sk, glob D} /\ SD.RO_G.m{1} = SD.H.m{2}).
  - rndsem*{2} 1.
  wp; rnd; wp; skip; rewrite /SD.keygen /SD.ds1 /SD.ds2 /=; auto.
  - auto => />; rewrite /SD.verify /=.
  move=> &2 [msg [w [zz hh]]] hm cc hc.
  case: (pk{2}) => aa tt /=.
  rewrite !FMap.get_set_sameE /=.
  split; move=> hmem r10 hr10; split; move=> hquery [hz [hhsize [hnorm hw]]].
  move: hquery; rewrite -hw FMap.mem_set /=.
  trivial.
  by rewrite -hw FMap.get_set_sameE /= hz hhsize hnorm.
  by move: hquery; rewrite -hw hmem.
  by rewrite -hw hz hhsize hnorm.
qed.

lemma commitment_set_bound sk (ws : high list list) :
  mu (SD.commit sk) (fun (wy : high list * vector) => wy.`1 \in ws) <=
  (size ws)%r * p_max (dfst (SD.commit sk)).
proof.
  have -> : mu (SD.commit sk) (fun (wy : high list * vector) => wy.`1 \in ws) =
            mu (dfst (SD.commit sk)) (mem ws).
  - by rewrite dmapE /(\o).
  apply (RealOrder.ler_trans
    (StdBigop.Bigreal.BRA.big predT (mu1 (dfst (SD.commit sk))) ws)).
  - exact mu_mem_le.
  apply (RealOrder.ler_trans
    (StdBigop.Bigreal.BRA.big predT (fun _ : high list => p_max (dfst (SD.commit sk))) ws)).
  - apply StdBigop.Bigreal.ler_sum_seq => w hw _; exact pmax_upper_bound.
  by rewrite StdBigop.Bigreal.sumr_const count_predT.
qed.

lemma respond_recovers pk sk wc c :
  (pk,sk) \in SD.keygen => wc \in SD.commit sk => c \in dC tau =>
  SD.respond sk c wc.`2 <> None =>
  wc.`1 = SD.recover pk c (oget (SD.respond sk c wc.`2)).
proof.
(* COMPLETE THIS *)
  case pk sk => [mA' t'] [mA s1 s2].
  move=> valid_keys.
  have sk_sizes : size mA = (k,l) /\ size s1 = l /\ size s2 = k.
  - apply SD.sk_size; by exists (mA',t').
  have [_ rg_s2] := SD.keygen_supp_decomp (mA',t') mA s1 s2 valid_keys.
  case /SD.pk_decomp valid_keys => [??]; subst.
  case wc => w0 y0.
  rewrite /SD.commit /= supp_dmap.
  move=> [y [y_supp [??]]] c_supp H; subst.
  move: H; rewrite /SD.respond /=.
  case: (inf_normv (y+c**s1) < gamma1-beta_ /\
    inf_normv (lowBitsV (mA *^ y-c**s2)) < gamma2-beta_) => // H _.
  rewrite /SD.recover /=.
  pose t := mA *^ s1 + s2.
  pose t1 := base2highbitsV t.
  pose t0 := base2lowbitsV t.
  pose w := mA *^ y.
  pose z := y + c ** s1.
  rewrite mulmxvDr mulmx_scalarv -/w.
  have W : w - c ** s2 = mA *^ z - c ** t0 - c ** base2shiftV t1.
  - rewrite /w /z mulmxvDr -!addvA; congr.
  rewrite mulmx_scalarv -!scalarvN -2!scalarvDr; congr.
  rewrite -oppvD [t0+_]addvC b2high_lowPv /t.
  have [szA [sz1 sz2]] := sk_sizes.
  rewrite oppvD addvA addvN size_mulmxv /=.
  rewrite lin_add0v // size_oppv sz2.
  by case szA.
  have W' : w - c ** s2 + c ** t0 = mA *^ z - c ** base2shiftV t1.
  - rewrite W -!addvA; congr.
  rewrite [_ + c**t0]addvC addvA [_ + c**t0]addvC addvN.
  rewrite lin_add0v // size_oppv.
  by rewrite !size_scalarv size_base2lowbitsV size_base2shiftV size_base2highbitsV.
  rewrite W'.
  have -> : w + c ** (mA *^ s1) = mA *^ z by rewrite /w /z mulmxvDr mulmx_scalarv.
  rewrite usehint_correctV.
  rewrite size_addv !size_oppv !size_scalarv size_base2shiftV size_mulmxv /t0 /t1 size_base2lowbitsV size_base2highbitsV /t size_addv size_mulmxv.
  have [szA [sz1 sz2]] := sk_sizes.
  case szA => rowsA colsA.
  by rewrite rowsA sz2 /max /#.
  have -> : 2*gamma2 %/ 2 = gamma2 by smt().
  rewrite inf_normvN.
  apply (IntOrder.ler_trans (tau * (2^d %/ 2))).
  apply l1_inf_norm_product_ub.
  smt(tau_bound).
  suff : 2 <= 2^d by smt().
  apply IntOrder.ler_eexpr => //; exact gt0_d.
  move: c_supp; rewrite DR.supp_dC; smt().
  have low_bound := DV.b2low_bound t.
  have pow_eq : 2 * 2^(d-1) = 2^d.
  have dp : 0 <= d-1 by smt(Params.gt0_d).
  have ep := Ring.IntID.exprS 2 (d-1) dp.
  smt().
  rewrite /t0 -pow_eq; smt().
  have half_le : (2^d %/ 2)*2 <= 2^d.
  - have eq := divz_eq (2^d) 2.
  have ge := modz_ge0 (2^d) 2.
  smt().
  have tau_pos : 0 < tau by smt(Params.tau_bound).
  have scaled : tau * ((2^d %/ 2)*2) <= tau * 2^d by rewrite IntOrder.ler_pmul2l.
  have ub := Params.ub_d.
  have combined : tau * ((2^d %/ 2)*2) <= 2 * gamma2 by exact (IntOrder.ler_trans _ _ _ scaled ub).
  move: combined; rewrite mulrA [2 * gamma2]mulrC IntOrder.ler_pmul2r //.
  rewrite -addvA [(_ - _)%Vectors]addvC addvA -W.
  have {1}-> : w = w - c**s2 + c**s2.
  - rewrite -addvA [_+c**s2]addvC addvN size_scalarv.
  rewrite addvC lin_add0v //.
  have [szA [sz1 sz2]] := sk_sizes.
  case szA => rowsA colsA.
  by rewrite /w size_mulmxv sz2 rowsA.
  have [C1 C2] {H} : inf_normv z < gamma1-beta_ /\ inf_normv (lowBitsV (mA *^ y - c ** s2)) < gamma2-beta_ by exact H.
  apply (hide_lowV _ _ beta_).
  have [szA [sz1 sz2]] := sk_sizes.
  case szA => rowsA colsA.
  by rewrite size_addv size_oppv !size_scalarv /w size_mulmxv rowsA sz2 /max /#.
  smt(Params.gt0_beta).
  smt(Params.beta_gamma2_lt).
  apply (IntOrder.ler_trans (tau * eta_)).
  apply l1_inf_norm_product_ub.
  - smt(Params.tau_bound).
  - smt(Params.gt0_eta).
  - move: c_supp; rewrite DR.supp_dC; smt().
  apply inf_normv_ler => [|i rg_i]; first by smt(Params.gt0_eta).
  move: rg_s2; rewrite /SD.ds2 supp_dvector; first by smt(Params.gt0_k).
  move=> [sz2 entries].
  rewrite -DR.supp_dRq; first by smt(Params.gt0_eta).
  apply entries; smt().
  by rewrite mulrC; exact Params.eta_tau_leq_b.
  have -> : 2 * gamma2 %/ 2 = gamma2 by smt().
  exact C2.
qed.

lemma cma_commitment_conversion &m :
 Pr[SD.FSaCR.DSS.EF_CMA_RO(SD.OpBasedSig, RedS(A), SD.H,
      SD.FSaCR.DSS.DS.Stateless.O_CMA_Default).main() @ &m : res] <=
 Pr[SD.EF_CMA_RO_G(SD.OpBasedSigG, SD.CG.RedFSaG(RedS(A)), SD.RO_G,
      SD.O_CMA_Default_G).main() @ &m : res].
proof.
(* COMPLETE THIS *)
  byequiv (_ : ={glob A} ==> res{1} => res{2}) => //.
  proc; inline *; wp.
  rnd; wp.
  call (_ : SD.H.m{1} = SD.RO_G.m{2} /\
    SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{1} = SD.O_CMA_Default_G.sk{2} /\
    SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.qs{1} = SD.O_CMA_Default_G.qs{2}).
  proc; inline *; wp.
  rnd{2}; wp.
  while (={m,sk,oz} /\ m0{1} = m1{2} /\ m{1} = m0{1} /\ m{2} = m0{2} /\
    w{1} = w0{2} /\ c{1} = c0{2} /\ SD.H.m{1} = SD.RO_G.m{2} /\
    SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.sk{1} = SD.O_CMA_Default_G.sk{2} /\
    SD.FSaCR.DSS.DS.Stateless.O_CMA_Default.qs{1} = SD.O_CMA_Default_G.qs{2} /\
    (oz{1} <> None => FMap."_.[_]" SD.H.m{1} (w{1},m{1}) = Some c{1})).
  - wp; rnd; wp; rnd; wp; skip.
  move=> &1 &2 />.
  move=> ws hws rr hr; rewrite !FMap.get_set_sameE /=.
  by move=> hin _; apply FMap.get_some.
  wp; skip; move=> &1 &2 />.
  move=> mr cr ozr wr _ _ hget rr hr; rewrite !FMap.domE hget /=.
  trivial.
  by proc; auto.
  wp; rnd; wp; skip; move=> &1 &2 />.
  by move=> ks hks rs mr qs rr hr; split; move=> _ hc _ hv _; rewrite -hc.
qed.

op external_budget = qH + qS + 1.

op trial_cost (e : real) (j t : int) =
  e * (j%r * (t+external_budget)%r / (1%r-p_rej) +
       (j*(j+1))%r / (2%r * (1%r-p_rej)^2)).

lemma trial_cost_unroll e j t :
  trial_cost e j t = (t+external_budget+1)%r * e +
    p_rej * trial_cost e j (t+1) +
    (1%r-p_rej) * trial_cost e (j-1) (t+1).
proof.
  have hp := rejection_range.
  have hne : 1%r-p_rej <> 0%r by smt().
  rewrite /trial_cost !fromintM !fromintD ?fromintB ?fromintN /=.
  move: hne; clear hp; move: p_rej => p hne.
  field; smt(RField.expr2).
qed.

lemma trial_cost_increment e j t :
  trial_cost e j t - trial_cost e (j-1) t =
  e * ((t+external_budget)%r / (1%r-p_rej) + j%r / (1%r-p_rej)^2).
proof.
  have hp := rejection_range.
  have hne : 1%r-p_rej <> 0%r by smt().
  rewrite /trial_cost !fromintM !fromintD ?fromintB ?fromintN /=.
  move: hne; clear hp; move: p_rej => p hne.
  field; smt(RField.expr2).
qed.

lemma trial_cost_ge0 e j t :
  0%r <= e => 0 <= j => 0 <= t => 0%r <= trial_cost e j t.
proof.
  move=> he hj ht.
  have hp := rejection_range.
  have hS := qS_ge0; have hH := qH_ge0.
  rewrite /trial_cost /external_budget.
  move: he hj ht hp hS hH; clear.
  move: p_rej qS qH => p qs qh he hj ht hp hS hH.
  apply mulr_ge0 => //.
  apply addr_ge0; apply divr_ge0; smt(RField.expr2).
qed.

lemma trial_cost_monotone e j t :
  0%r <= e => 1 <= j => 0 <= t =>
  trial_cost e (j-1) t <= trial_cost e j t.
proof.
  move=> he hj ht.
  have hp := rejection_range.
  have hS := qS_ge0; have hH := qH_ge0.
  rewrite -subr_ge0 trial_cost_increment /external_budget.
  move: he hj ht hp hS hH; clear.
  move: p_rej qS qH => p qs qh he hj ht hp hS hH.
  apply mulr_ge0 => //.
  apply addr_ge0; apply divr_ge0; smt(RField.expr2).
qed.

lemma trial_cost_drift e j t u v :
  0%r <= e => 1 <= j => 0 <= t => 0%r <= u <= p_rej =>
  v <= (t+external_budget)%r * e =>
  v + u * trial_cost e j (t+1) + (1%r-u) * trial_cost e (j-1) (t+1) <=
  trial_cost e j t.
proof.
  move=> he hj ht hu hv.
  have hm := trial_cost_monotone e j (t+1) he hj _; first smt().
  have heq := trial_cost_unroll e j t.
  move: he hu hv hm heq; clear.
  move: (trial_cost e j (t+1)) (trial_cost e (j-1) (t+1)) (trial_cost e j t) => a b c.
  move: p_rej external_budget => p B.
  rewrite !fromintD /=; smt().
qed.

lemma expected_indicator_choice (d : 'a distr) (hit p : 'a -> bool) a b :
  is_lossless d => 0%r <= a => 0%r <= b =>
  Xreal.Ep d (fun x => xr_ofreal (b2r (hit x) + if p x then a else b)) =
  xr_ofreal (mu d hit + mu d p*a + (1%r-mu d p)*b).
proof.
  move=> hd ha hb.
  have heq : forall x,
    xr_ofreal (b2r (hit x) + if p x then a else b) =
    Xreal.Rpbar.xadd (xr_ofreal (b2r (hit x)))
      (if p x then xr_ofreal a else xr_ofreal b).
  - move=> x.
    have hh : 0%r <= b2r (hit x) by case (hit x).
    case (p x) => _; rewrite /xr_ofreal /=.
    + by rewrite (Xreal.Rp.of_realD _ _ hh ha).
    + by rewrite (Xreal.Rp.of_realD _ _ hh hb).
  rewrite (Xreal.eq_Ep d _
    (fun x => Xreal.Rpbar.xadd (xr_ofreal (b2r (hit x)))
      (if p x then xr_ofreal a else xr_ofreal b))) 1:/#.
  rewrite Xreal.EpD Xreal.Ep_mu expected_choice //.
  have hm := mu_bounded d p; have hh := ge0_mu d hit.
  have hn : 0%r <= mu d p*a + (1%r-mu d p)*b by smt().
  have -> : mu d hit + mu d p*a + (1%r-mu d p)*b =
    mu d hit + (mu d p*a + (1%r-mu d p)*b) by ring.
  by rewrite /xr_ofreal (Xreal.Rp.of_realD _ _ hh hn).
qed.

local module Programmed : SD.CMAtoKOA.R1.Oracle_i = {
  var sk : SD.SK
  var table : (high list * M, Rq) FMap.fmap
  var countS, countH, nt : int
  var bad : bool

  proc init(sk_i : SD.SK) = {
    sk <- sk_i;
    table <- FMap.empty;
    countS <- 0; countH <- 0; nt <- 0; bad <- false;
  }

  proc h(w : high list, msg : M) = {
    var c, result;
    result <- witness;
    if (countH < external_budget) {
      countH <- countH+1;
      c <$ dC tau;
      if (!FMap.dom table (w,msg)) {
        table <- FMap."_.[_<-_]" table (w,msg) c;
      }
      result <- oget (FMap."_.[_]" table (w,msg));
    }
    return result;
  }

  proc sign(msg : M) = {
    var x, w, c, oz;
    w <- witness; c <- witness; oz <- None;
    if (countS < qS) {
      while (oz = None /\ !bad) {
        x <$ SD.commit sk `*` dC tau;
        w <- x.`1.`1; c <- x.`2;
        bad <- bad \/ FMap.dom table (w,msg);
        table <- FMap."_.[_<-_]" table (w,msg) c;
        oz <- SD.respond sk c x.`1.`2;
        nt <- nt+1;
      }
      countS <- countS+1;
    }
    return if bad then witness else (w,c,oget oz);
  }
}.

op programmed_inv (sk0 sk : SD.SK) ns nh nt (hm : (high list*M,Rq) FMap.fmap) =
  sk = sk0 /\ 0 <= ns <= qS /\ 0 <= nh <= external_budget /\
  0 <= nt /\ FMap.fsize hm <= nt+nh.

lemma commitment_table_bound sk (hm : (high list*M,Rq) FMap.fmap) msg :
  mu (SD.commit sk `*` dC tau)
    (fun (x : (high list*vector)*Rq) => FMap.dom hm (x.`1.`1,msg)) <=
  (FMap.fsize hm)%r * p_max (dfst (SD.commit sk)).
proof.
  rewrite (dprodEl (SD.commit sk) (dC tau)
    (fun wc : high list*vector => FMap.dom hm (wc.`1,msg))).
  have hC : is_lossless (dC tau).
  - apply dC_ll; have ht := tau_bound; move: ht; clear; smt().
  rewrite hC RField.mulr1.
  pose ws := map (fun x : high list*M => x.`1) (FSet.elems (FMap.fdom hm)).
  apply (RealOrder.ler_trans (mu (SD.commit sk) (fun wc : high list*vector => wc.`1 \in ws))).
  - apply mu_le => wc hw hhit.
    change (wc.`1 \in map (fun key : high list*M => key.`1) (FSet.elems (FMap.fdom hm))).
    apply (List.map_f (fun key : high list*M => key.`1)
      (FSet.elems (FMap.fdom hm)) (wc.`1,msg)).
    by rewrite -FSet.memE FMap.mem_fdom.
  have hb := commitment_set_bound sk ws.
  by move: hb; rewrite /ws size_map -FSet.cardE -/FMap.fsize.
qed.

lemma programmed_inv_hash sk0 sk ns nh nt hm key c :
  programmed_inv sk0 sk ns nh nt hm => nh < external_budget =>
  programmed_inv sk0 sk ns (nh+1) nt
    (if FMap.dom hm key then hm else FMap."_.[_<-_]" hm key c).
proof.
  rewrite /programmed_inv.
  case (FMap.dom hm key) => hmem; rewrite ?FMap.fsize_set.
  - move: qS external_budget => qs qh; smt().
  - move: qS external_budget => qs qh; smt().
qed.

lemma programmed_inv_step sk0 sk ns nh nt hm key c :
  programmed_inv sk0 sk ns nh nt hm =>
  programmed_inv sk0 sk ns nh (nt+1) (FMap."_.[_<-_]" hm key c).
proof.
  rewrite /programmed_inv FMap.fsize_set.
  move: qS external_budget => qs qh.
  case (FMap.dom hm key); smt().
qed.

lemma programmed_inv_count sk0 sk ns nh nt hm :
  programmed_inv sk0 sk ns nh nt hm => ns < qS =>
  programmed_inv sk0 sk (ns+1) nh nt hm.
proof.
  rewrite /programmed_inv.
  move: qS external_budget => qs qh; smt().
qed.

local lemma programmed_hash_cost sk0 :
  ehoare [Programmed.h :
    xr_guard (programmed_inv sk0 Programmed.sk Programmed.countS
      Programmed.countH Programmed.nt Programmed.table)
      (xr_ofreal (b2r Programmed.bad + trial_cost
        (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS) Programmed.nt)) ==>
    xr_guard (programmed_inv sk0 Programmed.sk Programmed.countS
      Programmed.countH Programmed.nt Programmed.table)
      (xr_ofreal (b2r Programmed.bad + trial_cost
        (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS) Programmed.nt))].
proof.
  proc; wp; skip.
  move=> &hr; apply Xreal.xle_cxr_r => hinv.
  case (Programmed.countH{hr} < external_budget) => hbudget /=.
  - have hg : forall c, programmed_inv sk0 Programmed.sk{hr}
      Programmed.countS{hr} (Programmed.countH{hr}+1) Programmed.nt{hr}
      (if FMap.dom Programmed.table{hr} (w{hr},msg{hr}) then Programmed.table{hr}
       else FMap."_.[_<-_]" Programmed.table{hr} (w{hr},msg{hr}) c).
    + move=> c; exact (programmed_inv_hash _ _ _ _ _ _ _ _ hinv hbudget).
    have heq : forall c,
      (if !FMap.dom Programmed.table{hr} (w{hr},msg{hr}) then
        xr_guard (programmed_inv sk0 Programmed.sk{hr} Programmed.countS{hr}
          (Programmed.countH{hr}+1) Programmed.nt{hr}
          (FMap."_.[_<-_]" Programmed.table{hr} (w{hr},msg{hr}) c))
          (xr_ofreal (b2r Programmed.bad{hr} + trial_cost
            (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS{hr}) Programmed.nt{hr}))
       else xr_guard (programmed_inv sk0 Programmed.sk{hr} Programmed.countS{hr}
          (Programmed.countH{hr}+1) Programmed.nt{hr} Programmed.table{hr})
          (xr_ofreal (b2r Programmed.bad{hr} + trial_cost
            (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS{hr}) Programmed.nt{hr}))) =
      xr_ofreal (b2r Programmed.bad{hr} + trial_cost
            (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS{hr}) Programmed.nt{hr}).
    + move=> c; have h := hg c.
      move: h; case (FMap.dom Programmed.table{hr} (w{hr},msg{hr})) => hmem /= h;
        by rewrite /xr_guard h.
    rewrite (Xreal.eq_Ep (dC tau) _ (fun _ =>
      xr_ofreal (b2r Programmed.bad{hr} + trial_cost
            (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS{hr}) Programmed.nt{hr}))).
    + move=> c hc; exact (heq c).
    rewrite Xreal.EpC.
    have hC : is_lossless (dC tau).
    + apply dC_ll; have ht := tau_bound; move: ht; clear; smt().
    by rewrite hC /xr_ofreal /=.
  by rewrite /xr_guard hinv.
qed.

local lemma programmed_sign_cost sk0 : SD.check sk0 =>
  ehoare [Programmed.sign :
    xr_guard (programmed_inv sk0 Programmed.sk Programmed.countS
      Programmed.countH Programmed.nt Programmed.table)
      (xr_ofreal (b2r Programmed.bad + trial_cost
        (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS) Programmed.nt)) ==>
    xr_guard (programmed_inv sk0 Programmed.sk Programmed.countS
      Programmed.countH Programmed.nt Programmed.table)
      (xr_ofreal (b2r Programmed.bad + trial_cost
        (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS) Programmed.nt))].
proof.
(* COMPLETE THIS *)
  move=> hsk.
  proc.
  seq 3 : (xr_guard (oz = None /\ programmed_inv sk0 Programmed.sk Programmed.countS
      Programmed.countH Programmed.nt Programmed.table)
      (xr_ofreal (b2r Programmed.bad + trial_cost
        (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS) Programmed.nt))).
  - wp; skip; simplify; trivial.
  if.
  - wp.
  while (xr_guard (Programmed.countS < qS /\ programmed_inv sk0 Programmed.sk Programmed.countS
      Programmed.countH Programmed.nt Programmed.table)
      (xr_ofreal (b2r Programmed.bad + trial_cost
        (p_max (dfst (SD.commit sk0)))
        (qS-Programmed.countS-b2i (oz <> None \/ Programmed.bad)) Programmed.nt))).
  + move=> &hr; apply Xreal.xle_cxr_r => hexit.
  apply Xreal.xle_cxr_r => -[hns hinv].
  have hdone : oz{hr} <> None \/ Programmed.bad{hr} by smt().
  have hi := programmed_inv_count _ _ _ _ _ _ hinv hns.
  rewrite hdone /= /xr_guard hi.
  have -> : qS-(Programmed.countS{hr}+1) = qS-Programmed.countS{hr}-1 by ring.
  by rewrite /b2i /= /xr_ofreal /=.
  wp; skip.
  move=> &hr; apply Xreal.xle_cxr_r => -[hoz hbad].
  apply Xreal.xle_cxr_r => -[hns hinv].
  have hkey : Programmed.sk{hr} = sk0 by move: hinv; rewrite /programmed_inv; move=> [-> _].
  move: hinv; rewrite hkey; move=> hinv.
  have hg : forall key c, programmed_inv sk0 sk0 Programmed.countS{hr}
      Programmed.countH{hr} (Programmed.nt{hr}+1)
      (FMap."_.[_<-_]" Programmed.table{hr} key c).
  - move=> key c; exact (programmed_inv_step _ _ _ _ _ _ _ _ hinv).
  have hb : Programmed.bad{hr} = false by move: hbad; case (Programmed.bad{hr}).
  rewrite hoz hb /xr_guard hns /= /b2r /b2i /=.
  have hguard : forall (x0 : (high list * vector) * Rq), programmed_inv sk0 sk0 Programmed.countS{hr} Programmed.countH{hr} (Programmed.nt{hr}+1) (FMap."_.[_<-_]" Programmed.table{hr} (x0.`1.`1,msg{hr}) x0.`2) by move=> x0; apply hg.
  rewrite (Xreal.eq_Ep _ _ (fun (x0 : (high list * vector) * Rq) => xr_ofreal (b2r (FMap.dom Programmed.table{hr} (x0.`1.`1,msg{hr})) + trial_cost (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS{hr} - b2i (SD.respond sk0 x0.`2 x0.`1.`2 <> None \/ FMap.dom Programmed.table{hr} (x0.`1.`1,msg{hr}))) (Programmed.nt{hr}+1))) _) ; first by move=> x hx; rewrite /= (hg (x.`1.`1,msg{hr}) x.`2) /b2i.
  pose e := p_max (dfst (SD.commit sk0)).
  pose j := qS-Programmed.countS{hr}.
  pose t := Programmed.nt{hr}.
  have he : 0%r <= e by apply ge0_pmax.
  have hj : 1 <= j by smt().
  have ht : 0 <= t by move: hinv; rewrite /programmed_inv; smt().
  have hm : trial_cost e (j-1) (t+1) <= trial_cost e j (t+1) by apply trial_cost_monotone; smt().
  have ha : 0%r <= trial_cost e j (t+1) by apply trial_cost_ge0; smt().
  have hc : 0%r <= trial_cost e (j-1) (t+1) by apply trial_cost_ge0; smt().
  apply (Xreal.Rpbar.xle_trans (Xreal.Ep (SD.commit sk0 `*` dC tau) (fun (x : (high list * vector) * Rq) => xr_ofreal (b2r (FMap.dom Programmed.table{hr} (x.`1.`1,msg{hr})) + if SD.respond sk0 x.`2 x.`1.`2 = None then trial_cost e j (t+1) else trial_cost e (j-1) (t+1))))).
  apply Xreal.le_Ep => x hx /=.
  case (SD.respond sk0 x.`2 x.`1.`2 = None); case (FMap.dom Programmed.table{hr} (x.`1.`1,msg{hr})) => /=; rewrite /b2i /b2r /=.
  move=> _ _.
  apply Xreal.Rpbar.xle_rle.
  move: hm ha hc.
  move: (trial_cost e (j-1) (t+1)) (trial_cost e j (t+1)) => a b.
  clear.
  smt().
  trivial.
  trivial.
  trivial.
  have hll : is_lossless (SD.commit sk0 `*` dC tau) by rewrite dprod_ll SD.commit_ll dC_ll //; smt(tau_bound).
  rewrite (expected_indicator_choice _ _ _ _ _ hll ha hc).
  pose u := mu (SD.commit sk0 `*` dC tau) (fun (x : (high list * vector) * Rq) => SD.respond sk0 x.`2 x.`1.`2 = None).
  pose v := mu (SD.commit sk0 `*` dC tau) (fun (x : (high list * vector) * Rq) => FMap.dom Programmed.table{hr} (x.`1.`1,msg{hr})).
  have hu01 : 0%r <= u <= 1%r by apply mu_bounded.
  have hv0 : 0%r <= v by apply ge0_mu.
  have hu : u <= p_rej by rewrite rejection_parameter; apply (SD.rej_bound sk0 hsk).
  have hv : v <= (FMap.fsize Programmed.table{hr})%r * e by apply commitment_table_bound.
  have hsize : FMap.fsize Programmed.table{hr} <= t + external_budget.
  move: hinv; rewrite /programmed_inv /t.
  move: (Programmed.countS{hr}) (Programmed.countH{hr}) (FMap.fsize Programmed.table{hr}) (Programmed.nt{hr}) external_budget qS => ns nh sz tt eb qs.
  clear.
  smt().
  have hvb : v <= (t+external_budget)%r * e.
  have hs : (FMap.fsize Programmed.table{hr})%r <= (t+external_budget)%r by rewrite le_fromint.
  move: hv he hs.
  rewrite /e /v.
  move: (p_max (dfst (SD.commit sk0))) (mu (SD.commit sk0 `*` dC tau) (fun (x : (high list * vector) * Rq) => FMap.dom Programmed.table{hr} (x.`1.`1,msg{hr}))) (FMap.fsize Programmed.table{hr})%r (t+external_budget)%r => ee vv nn mm.
  clear.
  smt().
  have hud : 0%r <= u <= p_rej by smt().
  have hd := trial_cost_drift e j t u v he hj ht hud hvb.
  apply Xreal.Rpbar.xle_rle; split.
  have hpos : forall (a b uu vv : real), 0%r <= a => 0%r <= b => 0%r <= uu <= 1%r => 0%r <= vv => 0%r <= vv + uu*a + (1%r-uu)*b by clear; smt().
  exact (hpos _ _ _ _ ha hc hu01 hv0).
  move=> _; exact hd.
  skip.
  move=> &hr.
  rewrite /xr_guard.
  case (Programmed.countS{hr} < qS) => hns /=.
  case (oz{hr} = None) => hoz /=; case (programmed_inv sk0 Programmed.sk{hr} Programmed.countS{hr} Programmed.countH{hr} Programmed.nt{hr} Programmed.table{hr}) => hinv /=.
  case (Programmed.bad{hr}) => hb; rewrite /b2i /b2r /=.
  have he := ge0_pmax (dfst (SD.commit sk0)).
  have hj : 1 <= qS-Programmed.countS{hr} by smt().
  have ht : 0 <= Programmed.nt{hr} by move: hinv; rewrite /programmed_inv; smt().
  have hm := trial_cost_monotone _ _ _ he hj ht.
  have hc : 0%r <= trial_cost (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS{hr}-1) Programmed.nt{hr} by apply trial_cost_ge0; smt().
  apply Xreal.Rpbar.xle_rle.
  move: hm hc.
  move: (trial_cost (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS{hr}-1) Programmed.nt{hr}) (trial_cost (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS{hr}) Programmed.nt{hr}) => a b.
  clear.
  smt().
  trivial.
  trivial.
  trivial.
  trivial.
  trivial.
  skip => &hr.
  rewrite /xr_guard.
  case (Programmed.countS{hr} < qS) => hns /=; case (oz{hr} = None) => hoz /=; case (programmed_inv sk0 Programmed.sk{hr} Programmed.countS{hr} Programmed.countH{hr} Programmed.nt{hr} Programmed.table{hr}) => hinv /=; trivial.
qed.

lemma commit_challenge_ll sk : is_lossless (SD.commit sk `*` dC tau).
proof.
  rewrite dprod_ll SD.commit_ll /=; apply dC_ll.
  have ht := tau_bound; move: ht; clear; smt().
qed.

lemma acceptance_probability sk : SD.check sk =>
  1%r-p_rej <= mu (SD.commit sk `*` dC tau)
    (fun (x : (high list*vector)*Rq) => SD.respond sk x.`2 x.`1.`2 <> None).
proof.
  move=> hsk; have hr := SD.rej_bound sk hsk.
  rewrite -rejection_parameter in hr.
  rewrite (mu_not (SD.commit sk `*` dC tau)
    (fun (x : (high list*vector)*Rq) => SD.respond sk x.`2 x.`1.`2 = None))
    (commit_challenge_ll sk).
  move: hr; clear.
  move: (mu (SD.commit sk `*` dC tau)
    (fun (x : (high list*vector)*Rq) => SD.respond sk x.`2 x.`1.`2 = None)) p_rej => r p.
  smt().
qed.

lemma trials_lossless sk0 : SD.check sk0 =>
  phoare [Trials.run : arg = sk0 ==> true] = 1%r.
proof.
  move=> hsk; proc.
  seq 2 : (sk = sk0) => //.
  - by auto.
  while (sk = sk0) (if oz = None then 1 else 0) 1 (1%r-p_rej).
  - trivial.
  - by rewrite /b2r.
  - move=> &hr oz hkey; case (oz = None); smt().
  - move=> ih; seq 3 : (sk = sk0) => //.
    + auto => />; apply commit_challenge_ll.
    + by hoare; auto.
  - auto => />; apply commit_challenge_ll.
  - split.
    + have hp := rejection_range; move: hp; clear; move: p_rej => p; smt().
    move=> z; wp; rnd; skip.
    move=> &hr [[hkey [hoz hz]] _]; split => //.
    have hz1 : 1 = z by move: hz; rewrite hoz.
    rewrite hkey -hz1.
    apply (RealOrder.ler_trans (mu (SD.commit sk0 `*` dC tau)
      (fun (x : (high list*vector)*Rq) => SD.respond sk0 x.`2 x.`1.`2 <> None))).
    + exact (acceptance_probability sk0 hsk).
    apply mu_le => x hx hc.
    change ((if SD.respond sk0 x.`2 x.`1.`2 = None then 1 else 0) < 1).
    by rewrite ifF //.
  by hoare; auto.
qed.

module type ROMCollisionPolicy = {
  proc entry() : SD.response_t option
  proc collision(sk : SD.SK, hm : (high list*M,Rq) FMap.fmap,
    key : high list*M, c : Rq, st : vector) : Rq * SD.response_t option
  proc finish(sig : high list*Rq*SD.response_t) : high list*Rq*SD.response_t
}.

module RawCollision : ROMCollisionPolicy = {
  proc entry() : SD.response_t option = { return None; }
  proc collision(sk : SD.SK, hm : (high list*M,Rq) FMap.fmap,
    key : high list*M, c : Rq, st : vector) = {
    c <- oget (FMap."_.[_]" hm key);
    return (c,SD.respond sk c st);
  }
  proc finish(sig : high list*Rq*SD.response_t) = { return sig; }
}.

module IndependentCollision : ROMCollisionPolicy = {
  proc entry() : SD.response_t option = { return None; }
  proc collision(sk : SD.SK, hm : (high list*M,Rq) FMap.fmap,
    key : high list*M, c : Rq, st : vector) = {
    return (c,SD.respond sk c st);
  }
  proc finish(sig : high list*Rq*SD.response_t) = { return sig; }
}.

module StopCollision : ROMCollisionPolicy = {
  proc entry() : SD.response_t option = { return Some witness; }
  proc collision(sk : SD.SK, hm : (high list*M,Rq) FMap.fmap,
    key : high list*M, c : Rq, st : vector) : Rq * SD.response_t option = {
    return (c,Some witness);
  }
  proc finish(sig : high list*Rq*SD.response_t) : high list*Rq*SD.response_t = { return witness; }
}.

local module Monitored (Policy : ROMCollisionPolicy) : SD.CMAtoKOA.R1.Oracle_i = {
  include var Programmed [init,h]

  proc sign(msg : M) = {
    var w,c,oz,x,result;
    w <- witness; c <- witness; oz <- None;
    if (countS < qS) {
      if (bad) { bad <- true; oz <@ Policy.entry(); }
      while (oz = None) {
        x <$ SD.commit sk `*` dC tau;
        w <- x.`1.`1; c <- x.`2;
        if (FMap.dom table (w,msg)) {
          bad <- true;
          (c,oz) <@ Policy.collision(sk,table,(w,msg),c,x.`1.`2);
        } else {
          oz <- SD.respond sk c x.`1.`2;
        }
        table <- FMap."_.[_<-_]" table (w,msg) c;
        nt <- nt+1;
      }
      countS <- countS+1;
    }
    result <- (w,c,oget oz);
    if (bad) { bad <- true; result <@ Policy.finish(result); }
    return result;
  }
}.

local lemma stop_sign_same : equiv [Programmed.sign ~ Monitored(StopCollision).sign :
  ={arg,glob Programmed} ==> ={res,glob Programmed}].
proof.
(* COMPLETE THIS *)
  proc; inline *; wp; sp; if => //.
  - case (Programmed.bad{1}).
  + rcondf{1} 1; first by auto.
  rcondt{2} 1; first by auto.
  rcondf{2} 3; first by auto.
  auto; smt().
  rcondf{2} 1; first by auto; smt().
  wp; while (={glob Programmed, w, c, msg} /\ (!Programmed.bad{1} => ={oz}) /\ (Programmed.bad{1} => oz{2} <> None)).
  wp; rnd; auto; smt().
  auto; smt().
qed.

module ROMHash (O : SD.CMAtoKOA.R1.Oracle) = {
  proc get(x : high list*M) = {
    var c;
    c <@ O.h(x.`1,x.`2);
    return c;
  }
}.

local module ROMSign (O : SD.CMAtoKOA.R1.Oracle) = {
  var qs : M list
  proc sign(msg : M) = {
    var w,c,z;
    qs <- rcons qs msg;
    (w,c,z) <@ O.sign(msg);
    return (w,z);
  }
}.

local module ROMAdversary (B : SD.FSaG.DSS.Adv_EFCMA_RO)
  (O : SD.CMAtoKOA.R1.Oracle) = {
  proc distinguish(pk : SD.PK) = {
    var msg,w,z,c,sig;
    ROMSign.qs <- [];
    (msg,sig) <@ B(ROMHash(O),ROMSign(O)).forge(pk);
    (w,z) <- sig;
    c <@ O.h(w,msg);
    return SD.verify pk w c z /\ !(msg \in ROMSign.qs);
  }
}.

op state_potential (sk0 sk : SD.SK) ns nh nt hm bad =
  xr_guard (programmed_inv sk0 sk ns nh nt hm)
    (xr_ofreal (b2r bad + trial_cost
      (p_max (dfst (SD.commit sk0))) (qS-ns) nt)).

lemma state_potential_dominates sk0 sk ns nh nt hm bad :
  Xreal.Rpbar.xle (xr_ofreal (b2r bad))
    (state_potential sk0 sk ns nh nt hm bad).
proof.
  apply Xreal.xle_cxr_r => hi.
  have [_ [hs [_ [ht _]]]] : programmed_inv sk0 sk ns nh nt hm by exact hi.
  have he := ge0_pmax (dfst (SD.commit sk0)).
  have hc := trial_cost_ge0 (p_max (dfst (SD.commit sk0))) (qS-ns) nt he _ ht; first smt().
  apply Xreal.Rpbar.xle_rle.
  have hb : 0%r <= b2r bad by case bad.
  move: hc hb; clear.
  move: (trial_cost (p_max (dfst (SD.commit sk0))) (qS-ns) nt) (b2r bad) => c b; smt().
qed.

local lemma rom_adversary_cost (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed}) sk0 :
  SD.check sk0 =>
  ehoare [ROMAdversary(B,Programmed).distinguish :
    state_potential sk0 Programmed.sk Programmed.countS Programmed.countH
      Programmed.nt Programmed.table Programmed.bad ==>
    state_potential sk0 Programmed.sk Programmed.countS Programmed.countH
      Programmed.nt Programmed.table Programmed.bad].
proof.
  move=> hsk; rewrite /state_potential; proc; wp.
  call (programmed_hash_cost sk0).
  wp.
  call (_ : xr_guard (programmed_inv sk0 Programmed.sk Programmed.countS
      Programmed.countH Programmed.nt Programmed.table)
      (xr_ofreal (b2r Programmed.bad + trial_cost
        (p_max (dfst (SD.commit sk0))) (qS-Programmed.countS) Programmed.nt))).
  - proc; wp; call (programmed_sign_cost sk0 hsk); wp; skip; trivial.
  - proc; wp; call (programmed_hash_cost sk0); wp; skip; trivial.
  wp; skip; trivial.
qed.

local module ProgrammedGame (B : SD.FSaG.DSS.Adv_EFCMA_RO) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var result;
    Programmed.init(sk);
    result <@ ROMAdversary(B,Programmed).distinguish(pk);
    return result;
  }
}.

local lemma programmed_game_bad (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed}) pk sk &m :
  SD.check sk =>
  Pr[ProgrammedGame(B).main(pk,sk) @ &m : Programmed.bad] <=
    trial_cost (p_max (dfst (SD.commit sk))) qS 0.
proof.
(* COMPLETE THIS *)
  move=> hsk.
  byehoare (_ : xr_guard (arg = (pk,sk))
    (xr_ofreal (trial_cost (p_max (dfst (SD.commit sk))) qS 0)) ==>
    xr_ofreal (b2r Programmed.bad)) => //.
  conseq (_ : xr_guard (arg = (pk,sk))
    (xr_ofreal (trial_cost (p_max (dfst (SD.commit sk))) qS 0)) ==>
    state_potential sk Programmed.sk Programmed.countS Programmed.countH
      Programmed.nt Programmed.table Programmed.bad).
  move=> &hr; apply Xreal.xle_cxr_l; first by move=> bad countH countS nt sk0 table; apply state_potential_dominates.
  by [].
  move=> &hr; apply Xreal.xle_cxr_r => _; apply state_potential_dominates.
  proc; call (rom_adversary_cost B sk hsk); inline Programmed.init; wp; skip.
  move=> &hr; apply Xreal.xle_cxr_r; move=> harg.
  have hskarg : sk{hr} = sk by smt().
  rewrite /state_potential /programmed_inv hskarg FMap.fsize_empty /= qS_ge0.
  apply Xreal.xle_cxr_l.
  move: harg => /= [hpk hsk']; rewrite hsk' /= /external_budget; smt(qS_ge0 qH_ge0).
  by [].
qed.

local module MonitoredGame (B : SD.FSaG.DSS.Adv_EFCMA_RO) (Policy : ROMCollisionPolicy) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var result;
    Programmed.sk <- sk;
    Programmed.table <- FMap.empty;
    Programmed.countS <- 0; Programmed.countH <- 0; Programmed.nt <- 0;
    Programmed.bad <- false;
    result <@ ROMAdversary(B,Monitored(Policy)).distinguish(pk);
    return result;
  }
}.

local lemma raw_stop_upto (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed}) pk sk &m :
  Pr[MonitoredGame(B,RawCollision).main(pk,sk) @ &m : res /\ !Programmed.bad] =
  Pr[MonitoredGame(B,StopCollision).main(pk,sk) @ &m : res /\ !Programmed.bad].
proof. byupto. qed.

local lemma independent_stop_upto (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed}) pk sk &m :
  Pr[MonitoredGame(B,IndependentCollision).main(pk,sk) @ &m : res /\ !Programmed.bad] =
  Pr[MonitoredGame(B,StopCollision).main(pk,sk) @ &m : res /\ !Programmed.bad].
proof. byupto. qed.

module FixedKOA = SD.CMAtoKOA.RedKOA(SD.CG.RedFSaG(RedS(A)),SD.HVZK_Sim_Inst).

lemma fixed_koa_lattice &m :
 Pr[SD.EF_KOA_RO_G(SD.OpBasedSigG, FixedKOA, SD.RO_G).main() @ &m : res] <=
   `|Pr[MLWE_L(RedMLWE(A)).main() @ &m : res] -
     Pr[MLWE_R(RedMLWE(A)).main() @ &m : res]| +
   Pr[SelfTargetMSIS(RedStMSIS(A), SD.RqStMSIS.PRO.RO).main() @ &m : res].
proof.
  have hr := koa_recovery FixedKOA &m.
  have he := koa_mlwe_left (SD.RedCR(FixedKOA)) &m.
  have hm := random_key_msis (SD.RedCR(FixedKOA)) &m.
  move: hr; rewrite he; move=> hr.
  have hn := RealOrder.ler_norm (Pr[MLWE_L(RedMLWE(A)).main() @ &m : res] -
    Pr[MLWE_R(RedMLWE(A)).main() @ &m : res]).
  smt().
qed.

local lemma programmed_sign_lossless sk0 : SD.check sk0 =>
  phoare [Programmed.sign : Programmed.sk = sk0 ==> true] = 1%r.
proof.
(* COMPLETE THIS *)
  move=> hsk; proc.
  seq 3 : (Programmed.sk = sk0) => //.
  - by auto.
  if; last by auto.
  wp.
  while (Programmed.sk = sk0)
    (if oz = None /\ !Programmed.bad then 1 else 0) 1 (1%r-p_rej).
  - trivial.
  - by rewrite /b2r.
  - move=> &hr bad oz hkey; case (oz = None /\ !bad); smt().
  - move=> ih; seq 7 : (Programmed.sk = sk0 /\ Programmed.countS < qS) => //.
  auto => />.
  move=> &hr _ _; exact (commit_challenge_ll sk0).
  hoare; auto.
  auto => />; move=> &hr _; exact (commit_challenge_ll sk0).
  split; first smt(rejection_range).
  move=> z; wp; rnd; skip.
  move=> &hr [[hkey [hguard hz]] _].
  rewrite hguard /= in hz; rewrite -hz hkey; split; last trivial.
  apply (RealOrder.ler_trans (mu (SD.commit sk0 `*` dC tau) (fun (x : (high list * vector) * Rq) => SD.respond sk0 x.`2 x.`1.`2 <> None))); first exact (acceptance_probability sk0 hsk).
  apply mu_le => x /=.
  move=> _ hx; rewrite hx /=.
  trivial.
  hoare; auto.
qed.

lemma ghost_counter_balance
  (H' <: SD.FSaG.DSS.Hash {-A,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS})
  (O' <: SD.FSaG.DSS.DS.Stateless.SOracle_CMA {-A,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [A(SD.CountH(SD.CMAtoKOA.CountH(H')),
    SD.CountS(SD.CG.OCR(SD.CMAtoKOA.CountH(H'),SD.CMAtoKOA.CountS(O')))).forge :
    SD.CMAtoKOA.CountH.qh = SD.CountH.qh + SD.CountS.qs /\
    SD.CMAtoKOA.CountS.qs = SD.CountS.qs ==>
    SD.CMAtoKOA.CountH.qh = SD.CountH.qh + SD.CountS.qs /\
    SD.CMAtoKOA.CountS.qs = SD.CountS.qs].
proof.
  proc (SD.CMAtoKOA.CountH.qh = SD.CountH.qh + SD.CountS.qs /\
    SD.CMAtoKOA.CountS.qs = SD.CountS.qs) => //.
  - proc; inline *; wp; call (_ : true); wp; call (_ : true); wp; skip; smt().
  - proc; inline *; wp; call (_ : true); wp; skip; smt().
qed.

lemma ghost_adversary_budget
  (H' <: SD.FSaG.DSS.Hash {-A,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS})
  (O' <: SD.FSaG.DSS.DS.Stateless.SOracle_CMA {-A,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [A(SD.CountH(SD.CMAtoKOA.CountH(H')),
    SD.CountS(SD.CG.OCR(SD.CMAtoKOA.CountH(H'),SD.CMAtoKOA.CountS(O')))).forge :
    SD.CountH.qh = 0 /\ SD.CountS.qs = 0 /\
    SD.CMAtoKOA.CountH.qh = 0 /\ SD.CMAtoKOA.CountS.qs = 0 ==>
    SD.CMAtoKOA.CountH.qh <= qH+qS /\ SD.CMAtoKOA.CountS.qs <= qS].
proof.
  conseq (A_bound (SD.CMAtoKOA.CountH(H'))
    (SD.CG.OCR(SD.CMAtoKOA.CountH(H'),SD.CMAtoKOA.CountS(O'))))
    (ghost_counter_balance H' O'); smt().
qed.

op trial_reject (sk : SD.SK) (x : (high list*vector)*Rq) =
  SD.respond sk x.`2 x.`1.`2 = None.

module SingleTrial = {
  proc draw(sk : SD.SK) = {
    var x;
    x <$ SD.commit sk `*` dC tau;
    return x;
  }
}.

module SplitTrial = {
  proc draw(sk : SD.SK) = {
    var b,x;
    b <$ DBool.Biased.dbiased (mu (SD.commit sk `*` dC tau) (trial_reject sk));
    x <$ if b then dcond (SD.commit sk `*` dC tau) (trial_reject sk)
         else dcond (SD.commit sk `*` dC tau) (predC (trial_reject sk));
    return x;
  }
}.

lemma split_trial_equiv : equiv [SingleTrial.draw ~ SplitTrial.draw :
  ={arg} ==> ={res}].
proof.
  proc; rndsem*{2} 0; rnd; skip.
  move=> &1 &2 />.
  have hk :
    (fun b : bool => dmap
      (if b then dcond (SD.commit sk{2} `*` dC tau) (trial_reject sk{2})
       else dcond (SD.commit sk{2} `*` dC tau) (predC (trial_reject sk{2})))
      (fun x : (high list*vector)*Rq => x)) =
    (fun b : bool => if b then dcond (SD.commit sk{2} `*` dC tau) (trial_reject sk{2})
       else dcond (SD.commit sk{2} `*` dC tau) (predC (trial_reject sk{2}))).
  - apply fun_ext => b; apply Distr.dmap_id.
  rewrite hk.
  rewrite -(marginal_sampling_pred (SD.commit sk{2} `*` dC tau)
    (trial_reject sk{2}) (commit_challenge_ll sk{2})).
  trivial.
qed.

module type TrialSampler = {
  proc draw(sk : SD.SK) : (high list*vector)*Rq
}.

module LoggedTrials (T : TrialSampler) = {
  proc run(sk : SD.SK) = {
    var x,log;
    log <- [];
    x <@ T.draw(sk);
    while (trial_reject sk x) {
      log <- rcons log x;
      x <@ T.draw(sk);
    }
    return (log,x);
  }
}.

module FactoredTrials = {
  proc run(sk : SD.SK) = {
    var b,x,log;
    log <- [];
    b <$ DBool.Biased.dbiased (mu (SD.commit sk `*` dC tau) (trial_reject sk));
    while (b) {
      x <$ dcond (SD.commit sk `*` dC tau) (trial_reject sk);
      log <- rcons log x;
      b <$ DBool.Biased.dbiased (mu (SD.commit sk `*` dC tau) (trial_reject sk));
    }
    x <$ dcond (SD.commit sk `*` dC tau) (predC (trial_reject sk));
    return (log,x);
  }
}.

lemma logged_trials_factorization : equiv
  [LoggedTrials(SingleTrial).run ~ FactoredTrials.run :
    ={arg} /\ SD.check arg{1} ==> ={res}].
proof.
(* COMPLETE THIS *)
  transitivity LoggedTrials(SplitTrial).run
    (={arg} ==> ={res}) (={arg} /\ SD.check arg{1} ==> ={res}) => //.
  - by move=> &1 &2 [-> hcheck]; exists arg{2}.
  - proc; while (={sk,x,log}); wp; call split_trial_equiv; auto.
  proc; inline SplitTrial.draw.
  transitivity* {1} { log <- []; b <$ DBool.Biased.dbiased (mu (SD.commit sk `*` dC tau) (trial_reject sk)); x <$ if b then dcond (SD.commit sk `*` dC tau) (trial_reject sk) else dcond (SD.commit sk `*` dC tau) (predC (trial_reject sk)); while (b) { log <- rcons log x; b <$ DBool.Biased.dbiased (mu (SD.commit sk `*` dC tau) (trial_reject sk)); x <$ if b then dcond (SD.commit sk `*` dC tau) (trial_reject sk) else dcond (SD.commit sk `*` dC tau) (predC (trial_reject sk)); } }.
  while (={sk,log,x} /\ trial_reject sk{1} x{1} = b{2}); wp; rnd; wp; rnd; wp; skip; progress.
  case b0L => Hb.
  move: H3.
  rewrite Hb /= dcond_supp; by move=> [_ ->].
  move: H3; rewrite Hb /= dcond_supp /predC; by move=> [_ ->].
  case b0L => // Hb; move: H3; by rewrite Hb /= dcond_supp /predC H5 /=.
  move: H3; rewrite H5 /= dcond_supp; by move=> [_ ->].
  case bL => Hb; move: H2; rewrite Hb /= dcond_supp /predC; by move=> [_ ->].
  case bL => // Hb; move: H2; by rewrite Hb /= dcond_supp /predC H4 /=.
  move: H2; rewrite H4 /= dcond_supp; by move=> [_ ->].
  seq 2 2 : (={sk,log,b} /\ SD.check sk{1}); first by auto.
  transitivity* {2} { while (b) { x <$ if b then dcond (SD.commit sk `*` dC tau) (trial_reject sk) else dcond (SD.commit sk `*` dC tau) (predC (trial_reject sk)); log <- rcons log x; b <$ DBool.Biased.dbiased (mu (SD.commit sk `*` dC tau) (trial_reject sk)); } x <$ if b then dcond (SD.commit sk `*` dC tau) (trial_reject sk) else dcond (SD.commit sk `*` dC tau) (predC (trial_reject sk)); }.
  transitivity* {1} { x <- witness; x <$ if b then dcond (SD.commit sk `*` dC tau) (trial_reject sk) else dcond (SD.commit sk `*` dC tau) (predC (trial_reject sk)); while (b) { log <- rcons log x; b <$ DBool.Biased.dbiased (mu (SD.commit sk `*` dC tau) (trial_reject sk)); x <$ if b then dcond (SD.commit sk `*` dC tau) (trial_reject sk) else dcond (SD.commit sk `*` dC tau) (predC (trial_reject sk)); } }; first by while (={sk,log,b,x}); auto.
  transitivity* {2} { x <- witness; while (b) { x <$ if b then dcond (SD.commit sk `*` dC tau) (trial_reject sk) else dcond (SD.commit sk `*` dC tau) (predC (trial_reject sk)); log <- rcons log x; b <$ DBool.Biased.dbiased (mu (SD.commit sk `*` dC tau) (trial_reject sk)); } x <$ if b then dcond (SD.commit sk `*` dC tau) (trial_reject sk) else dcond (SD.commit sk `*` dC tau) (predC (trial_reject sk)); }.
  seq 1 1 : (={sk,log,b,x}); first by auto.
  eager while (={sk,log,b,x}).
  by progress.
  by auto.
  by move=> &2 b0; auto.
  by auto.
  by auto.
  by auto.
  rnd; while (={sk,log,b}); by auto.
  rnd; while (={sk,log,b}); by auto=> />.
qed.

op log_hit_cost (sk : SD.SK) (ws : high list list) =
  (size ws)%r * p_max (dfst (SD.commit sk)) / (1%r-p_rej).

lemma log_hit_cost_ge0 sk ws : 0%r <= log_hit_cost sk ws.
proof.
  rewrite /log_hit_cost.
  have hp := rejection_range; have he := ge0_pmax (dfst (SD.commit sk)).
  have hsint := List.size_ge0 ws.
  have hs : 0%r <= (size ws)%r by smt().
  move: hp he hs; clear; move: p_rej (p_max (dfst (SD.commit sk))) (size ws)%r => p e s.
  smt(RealOrder.divr_ge0 RealOrder.mulr_ge0).
qed.

lemma rejected_hit_drift sk (ws : high list list) n : SD.check sk => 0%r <= n =>
  Xreal.Rpbar.xle
    (Xreal.Ep (SD.commit sk `*` dC tau)
      (fun x : (high list*vector)*Rq => xr_ofreal
        (n + if trial_reject sk x then b2r (x.`1.`1 \in ws) + log_hit_cost sk ws else 0%r)))
    (xr_ofreal (n+log_hit_cost sk ws)).
proof.
(* COMPLETE THIS *)
  move=> hsk hn.
  have hc := log_hit_cost_ge0 sk ws.
  have heq :
    (fun x : (high list*vector)*Rq => xr_ofreal
      (n + if trial_reject sk x then b2r (x.`1.`1 \in ws) + log_hit_cost sk ws else 0%r)) =
    (fun x : (high list*vector)*Rq => xr_ofreal
      (b2r (trial_reject sk x /\ x.`1.`1 \in ws) +
       if trial_reject sk x then n+log_hit_cost sk ws else n)).
  - apply fun_ext => x; congr.
  case (trial_reject sk x).
  move=> _; rewrite /=; ring.
  move=> _; rewrite /b2r /=.
  trivial.
  rewrite heq expected_indicator_choice.
  rewrite dprod_ll SD.commit_ll /=; apply dC_ll.
  have [ht0 htn] := tau_bound; split.
  exact (IntOrder.ler_trans 1 0 tau _ ht0).
  move=> _; exact htn.
  exact (RealOrder.addr_ge0 _ _ hn hc).
  exact hn.
  apply Xreal.Rpbar.xle_rle.
  pose u := mu (SD.commit sk `*` dC tau) (fun x => trial_reject sk x); pose v := mu (SD.commit sk `*` dC tau) (fun x => trial_reject sk x /\ x.`1.`1 \in ws).
  have hu : u <= p_rej by rewrite /u /trial_reject rejection_parameter; exact (SD.rej_bound sk hsk).
  have hv0 : v <= mu (SD.commit sk `*` dC tau) (fun (x : (high list * vector) * Rq) => x.`1.`1 \in ws) by apply mu_le => x _ [_ hx]; exact hx.
  have hll : is_lossless (dC tau) by apply dC_ll; have [ht0 htn] := tau_bound; split; [exact (IntOrder.ler_trans 1 0 tau _ ht0) | move=> _; exact htn].
  rewrite (dprodEl _ _ (fun (wy : high list * vector) => wy.`1 \in ws)) in hv0.
  move: hv0; rewrite hll /= => hv0; have hv := RealOrder.ler_trans _ _ _ hv0 (commitment_set_bound sk ws).
  have [hu0 hu1] := mu_bounded (SD.commit sk `*` dC tau) (fun x => trial_reject sk x); have [hvpos hv1] := mu_bounded (SD.commit sk `*` dC tau) (fun x => trial_reject sk x /\ x.`1.`1 \in ws).
  have hid : v + u * (n + log_hit_cost sk ws) + (1%r-u)*n = n + (v + u * log_hit_cost sk ws) by ring; rewrite hid; split.
  rewrite hid; split.
  exact (RealOrder.addr_ge0 _ _ hn (RealOrder.addr_ge0 _ _ hvpos (RealOrder.mulr_ge0 _ _ hu0 hc))).
  move=> _; rewrite RealOrder.ler_add2l; have [hp0 hp1] := rejection_range.
  have hdpos : 0%r < 1%r-p_rej by rewrite RealOrder.subr_gt0; exact hp1.
  have hd := RealOrder.gtr_eqF _ _ hdpos; have hmul := RealOrder.ler_wpmul2r _ hc _ _ hu.
  have hcost : (size ws)%r * p_max (dfst (SD.commit sk)) + p_rej * log_hit_cost sk ws = log_hit_cost sk ws.
  rewrite /log_hit_cost; field; exact hd.
  have hsum := RealOrder.ler_add _ _ _ _ hv hmul; rewrite hcost in hsum; exact hsum.
qed.

lemma logged_trials_hit_cost sk0 (ws : high list list) : SD.check sk0 =>
  ehoare [LoggedTrials(SingleTrial).run :
    xr_guard (arg = sk0) (xr_ofreal (log_hit_cost sk0 ws)) ==>
    xr_ofreal ((count (fun x : (high list*vector)*Rq => x.`1.`1 \in ws) res.`1)%r)].
proof.
(* COMPLETE THIS *)
  move=> hsk; proc; inline SingleTrial.draw.
  while (xr_guard (sk = sk0)
    (xr_ofreal ((count (fun x : (high list*vector)*Rq => x.`1.`1 \in ws) log)%r +
      if trial_reject sk0 x then b2r (x.`1.`1 \in ws) + log_hit_cost sk0 ws else 0%r))).
  - move=> &hr; apply Xreal.xle_cxr_r => hexit.
  apply Xreal.xle_cxr_r => hkey.
  have hx : !trial_reject sk0 x{hr} by move: hexit; rewrite hkey.
  by rewrite ifF //.
  wp.
  skip.
  move=> &hr; apply Xreal.xle_cxr_r => hre; case (sk{hr} = sk0) => hsame.
  rewrite /xr_guard /= -hsame hre /= hsame.
  rewrite -cats1 count_cat /=.
  rewrite fromintD -b2rE.
  rewrite Real.RField.addrA; apply rejected_hit_drift => //.
  apply RealOrder.addr_ge0; [by rewrite le_fromint; apply count_ge0 | exact: b2r_ge0].
  by rewrite /xr_guard /=.
  wp; skip; move=> &hr; case (sk{hr} = sk0) => hsame.
  rewrite /xr_guard /= hsame; exact: (rejected_hit_drift sk0 ws 0%r hsk _).
  by rewrite /xr_guard /=.
qed.

lemma xr_add a b : 0%r <= a => 0%r <= b =>
  xr_ofreal (a+b) = Xreal.Rpbar.xadd (xr_ofreal a) (xr_ofreal b).
proof.
  move=> ha hb; rewrite /xr_ofreal (Xreal.Rp.of_realD a b ha hb).
  trivial.
qed.

lemma logged_trials_hit_cost_offset sk0 (ws : high list list) n :
  SD.check sk0 => 0%r <= n =>
  ehoare [LoggedTrials(SingleTrial).run :
    xr_guard (arg = sk0) (xr_ofreal (n+log_hit_cost sk0 ws)) ==>
    xr_ofreal (n+(count (fun x : (high list*vector)*Rq => x.`1.`1 \in ws) res.`1)%r)].
proof.
  move=> hsk hn.
  conseq / (fun x : Xreal.Rpbar.xreal => Xreal.Rpbar.xadd (xr_ofreal n) x)
    (logged_trials_hit_cost sk0 ws hsk).
  - move=> &hr; apply Xreal.xle_cxr_r => harg.
    rewrite /xr_guard harg (xr_add n _ hn (log_hit_cost_ge0 sk0 ws)).
    trivial.
  - move=> &hr.
    have hc := List.count_ge0 (fun x : (high list*vector)*Rq => x.`1.`1 \in ws) res{hr}.`1.
    have hcr : 0%r <= (count (fun x : (high list*vector)*Rq => x.`1.`1 \in ws) res{hr}.`1)%r
      by rewrite le_fromint; apply List.count_ge0.
    by rewrite (xr_add n _ hn hcr).
qed.

lemma trials_logged_termination : equiv
  [Trials.run ~ LoggedTrials(SingleTrial).run : ={arg} ==> true].
proof.
  proc; inline SingleTrial.draw.
  unroll{1} 3; rcondt{1} 3; first by auto.
  wp; while (={sk} /\ oz{1} = SD.respond sk{2} x{2}.`2 x{2}.`1.`2).
  - wp; rnd; auto.
  auto.
qed.

lemma logged_trials_lossless sk0 : SD.check sk0 =>
  phoare [LoggedTrials(SingleTrial).run : arg = sk0 ==> true] = 1%r.
proof.
  move=> hsk.
  have ht := trials_lossless sk0 hsk.
  have he : equiv [LoggedTrials(SingleTrial).run ~ Trials.run : ={arg} ==> true].
  - symmetry; conseq trials_logged_termination; smt().
  conseq he ht; smt().
qed.

module BatchLogs = {
  proc run(sk : SD.SK, n : int) = {
    var i,logs,ls,x;
    i <- 0; logs <- [];
    while (i < n) {
      (ls,x) <@ LoggedTrials(SingleTrial).run(sk);
      logs <- rcons logs ls;
      i <- i+1;
    }
    return logs;
  }
}.

lemma batch_logs_lossless sk0 n0 : SD.check sk0 =>
  phoare [BatchLogs.run : arg = (sk0,n0) ==> true] = 1%r.
proof.
  move=> hsk; proc.
  while (sk=sk0 /\ n=n0) (n-i).
  - move=> z; wp.
    call (logged_trials_lossless sk0 hsk).
    skip; smt().
  auto; smt().
qed.

op batch_hits (ws : high list list) (logs : ((high list*vector)*Rq) list list) =
  count (fun x : (high list*vector)*Rq => x.`1.`1 \in ws) (flatten logs).

lemma batch_hits_ge0 ws logs : 0 <= batch_hits ws logs.
proof. rewrite /batch_hits; apply List.count_ge0. qed.

lemma batch_hits_rcons ws logs ls :
  batch_hits ws (rcons logs ls) = batch_hits ws logs +
    count (fun x : (high list*vector)*Rq => x.`1.`1 \in ws) ls.
proof. by rewrite /batch_hits flatten_rcons count_cat. qed.

lemma batch_logs_hit_cost sk0 (ws : high list list) n0 :
  SD.check sk0 => 0 <= n0 =>
  ehoare [BatchLogs.run : xr_guard (arg=(sk0,n0))
      (xr_ofreal (n0%r*log_hit_cost sk0 ws)) ==>
    xr_ofreal ((batch_hits ws res)%r)].
proof.
(* COMPLETE THIS *)
  move=> hsk hn; proc.
  while (xr_guard (sk=sk0 /\ n=n0 /\ 0<=i<=n0)
    (xr_ofreal ((batch_hits ws logs)%r+(n0-i)%r*log_hit_cost sk0 ws))).
  - move=> &hr; apply Xreal.xle_cxr_r => hexit.
  rewrite /xr_guard.
  case (sk{hr}=sk0 /\ n{hr}=n0 /\ 0<=i{hr}<=n0) => hinv /=.
  + have heq : i{hr}=n0 by smt().
  by rewrite heq /=.
  trivial.
  wp.
  exlim logs => logs0; exlim i => i0.
  have [hi0|hi0] : (0 <= i0 < n0) \/ !(0 <= i0 < n0) by smt().
  conseq (_ : xr_guard (sk = sk0) (xr_ofreal ((batch_hits ws logs0)%r + (n0 - i0 - 1)%r * log_hit_cost sk0 ws + log_hit_cost sk0 ws)) ==> xr_ofreal ((batch_hits ws logs0)%r + (n0 - i0 - 1)%r * log_hit_cost sk0 ws + (count (fun x : (high list*vector)*Rq => x.`1.`1 \in ws) ls)%r)).
  move=> &hr; apply Xreal.xle_cxr_r => hi; apply Xreal.xle_cxr_r => hl; apply Xreal.xle_cxr_r => hlt.
  rewrite /xr_guard; case: (sk{hr} = sk0 /\ n{hr} = n0 /\ 0 <= i{hr} <= n0) => hg; last by trivial.
  apply Xreal.xle_cxr_l.
  move=> ls0; have hg1 : sk{hr} = sk0 /\ n{hr} = n0 /\ 0 <= i{hr} + 1 <= n0 by smt().
  rewrite /= hg1 /= batch_hits_rcons fromintD -hl -hi.
  have -> : n0 - (i0 + 1) = n0 - i0 - 1 by ring.
  have -> : (batch_hits ws logs0)%r + (count (fun (x0 : (high list * vector) * Rq) => x0.`1.`1 \in ws) ls0)%r + (n0 - i0 - 1)%r * log_hit_cost sk0 ws = (batch_hits ws logs0)%r + (n0 - i0 - 1)%r * log_hit_cost sk0 ws + (count (fun (x0 : (high list * vector) * Rq) => x0.`1.`1 \in ws) ls0)%r by ring.
  trivial.
  have hkey : sk{hr} = sk0 by smt().
  rewrite hkey /= -hl -hi.
  have -> : (batch_hits ws logs0)%r + (n0 - i0 - 1)%r * log_hit_cost sk0 ws + log_hit_cost sk0 ws = (batch_hits ws logs0)%r + (n0 - i0)%r * log_hit_cost sk0 ws by rewrite !fromintB; ring.
  trivial.
  move=> &hr; apply Xreal.xle_cxr_r => h; exact (h ls{hr}).
  have hoff : 0%r <= (batch_hits ws logs0)%r + (n0 - i0 - 1)%r * log_hit_cost sk0 ws.
  have hb : 0%r <= (batch_hits ws logs0)%r by rewrite le_fromint; exact (batch_hits_ge0 ws logs0).
  have hnrem : 0%r <= (n0 - i0 - 1)%r by rewrite le_fromint; smt().
  have hc := log_hit_cost_ge0 sk0 ws.
  apply addr_ge0; first exact hb.
  exact (mulr_ge0 _ _ hnrem hc).
  conseq (_ : _ ==> xr_ofreal ((batch_hits ws logs0)%r + (n0 - i0 - 1)%r * log_hit_cost sk0 ws + (count (fun x : (high list*vector)*Rq => x.`1.`1 \in ws) (ls,x).`1)%r)).
  by move=> &hr; apply Xreal.xle_cxr_l; trivial.
  by move=> &hr; apply Xreal.xle_cxr_r; trivial.
  call (logged_trials_hit_cost_offset sk0 ws ((batch_hits ws logs0)%r + (n0 - i0 - 1)%r * log_hit_cost sk0 ws) hsk hoff).
  skip; trivial.
  conseq (_ : Xreal.Rpbar.oo ==> Xreal.Rpbar.oo).
  move=> &hr; apply Xreal.xle_cxr_r => hi; apply Xreal.xle_cxr_r => hl; apply Xreal.xle_cxr_r => hlt.
  have hg : !(sk{hr} = sk0 /\ n{hr} = n0 /\ 0 <= i{hr} <= n0) by smt().
  rewrite /xr_guard hg /=; trivial.
  by move=> &hr; apply Xreal.xle_cxr_r; trivial.
  inline LoggedTrials(SingleTrial).run SingleTrial.draw.
  wp.
  while (Xreal.Rpbar.oo).
  by move=> &hr; apply Xreal.xle_cxr_r; trivial.
  wp.
  skip; move=> &hr; apply Xreal.xle_cxr_r; trivial.
  wp; skip; trivial.
  wp; skip; move=> &hr; rewrite /xr_guard /batch_hits /=.
  rewrite hn /= /flatten /count /=; trivial.
qed.

op trial_transcript (sk : SD.SK) (x : (high list*vector)*Rq) =
  omap (fun z => (x.`1.`1,x.`2,z)) (SD.respond sk x.`2 x.`1.`2).

module DirectTranscript = {
  proc get_trans(pk : SD.PK, sk : SD.SK) = {
    var x;
    x <$ SD.commit sk `*` dC tau;
    return trial_transcript sk x;
  }
}.

module AcceptedTranscript = {
  proc run(sk : SD.SK) = {
    var x,ls;
    (ls,x) <@ LoggedTrials(SingleTrial).run(sk);
    return oget (trial_transcript sk x);
  }
}.

module DirectTranscriptLoop = {
  proc run(pk : SD.PK, sk : SD.SK) = {
    var ot;
    ot <- None;
    while (ot = None) { ot <@ DirectTranscript.get_trans(pk,sk); }
    return oget ot;
  }
}.

module HonestTranscriptLoop = {
  proc run(pk : SD.PK, sk : SD.SK) = {
    var ot;
    ot <- None;
    while (ot = None) {
      ot <@ SD.DID.Honest_Execution(SD.OpBased.P,SD.OpBased.V).get_trans(pk,sk);
    }
    return oget ot;
  }
}.

module SimTranscriptLoop = {
  proc run(pk : SD.PK) = {
    var ot;
    ot <- None;
    while (ot = None) { ot <@ SD.HVZK_Sim_Inst.get_trans(pk); }
    return oget ot;
  }
}.

lemma direct_honest_trial : equiv
  [DirectTranscript.get_trans ~
   SD.DID.Honest_Execution(SD.OpBased.P,SD.OpBased.V).get_trans :
   ={arg} ==> ={res}].
proof.
(* COMPLETE THIS *)
  proc; inline *; wp.
  rndsem*{2} 0.
  rnd (fun (x : (SD.commit_t * SD.pstate_t) * SD.challenge_t) => (x.`1.`2, x.`1.`1, x.`2)) (fun (x : SD.pstate_t * SD.commit_t * SD.challenge_t) => ((x.`2, x.`1), x.`3)).
  auto => />.
  move=> &2; rewrite -(dmap_dprodE (SD.commit sk{2}) (dC tau) (fun (x : (SD.commit_t * SD.pstate_t) * SD.challenge_t) => (x.`1.`2, x.`1.`1, x.`2))).
  split; first by move=> [s w c] /=.
  move=> _; split.
  move=> p hp; apply (dmap1E_can _ _ (fun (x : SD.pstate_t * SD.commit_t * SD.challenge_t) => ((x.`2, x.`1), x.`3))); first by move=> [s w c].
  by move=> [[w s] c].
  move=> _ [[w s] c] hx /=; split; first by rewrite supp_dmap; exists ((w,s),c).
  move=> _; rewrite /trial_transcript /=; case (SD.respond sk{2} c s) => //=.
qed.

lemma trial_transcript_none sk x :
  (trial_transcript sk x = None) = trial_reject sk x.
proof.
  rewrite /trial_transcript /trial_reject.
  by case (SD.respond sk x.`2 x.`1.`2).
qed.

lemma honest_simulated_loop pk0 sk0 : (pk0,sk0) \in SD.keygen =>
  equiv [HonestTranscriptLoop.run ~ SimTranscriptLoop.run :
    arg{1}=(pk0,sk0) /\ arg{2}=pk0 ==> ={res}].
proof.
  move=> hkey; proc.
  while (pk{1}=pk0 /\ sk{1}=sk0 /\ pk{2}=pk0 /\ ={ot}).
  - call (SD.HVZK_Sim_correct (pk0,sk0)); auto.
  auto.
qed.

lemma accepted_direct_loop : equiv
  [AcceptedTranscript.run ~ DirectTranscriptLoop.run :
    sk{1}=sk{2} ==> ={res}].
proof.
(* COMPLETE THIS *)
  proc; inline LoggedTrials(SingleTrial).run SingleTrial.draw DirectTranscript.get_trans.
  unroll{2} 2; rcondt{2} 2; first by auto.
  wp.
  while (={sk} /\ sk0{1}=sk{1} /\ ot{2}=trial_transcript sk{1} x0{1}).
  - wp; rnd; auto.
  move=> &1 &2 [[hsk [hsk0 hot]] _].
  rewrite hsk0 hsk.
  split; first by auto.
  move=> x hx.
  rewrite trial_transcript_none.
  by auto.
  wp; rnd; wp; skip.
  move=> &1 &2 /= hsk.
  rewrite hsk /=.
  move=> x hx.
  rewrite trial_transcript_none hx /=.
  move=> x0 ot _ _ ->.
  by trivial.
qed.

lemma direct_simulated_loop pk0 sk0 : (pk0,sk0) \in SD.keygen =>
  equiv [DirectTranscriptLoop.run ~ SimTranscriptLoop.run :
    arg{1}=(pk0,sk0) /\ arg{2}=pk0 ==> ={res}].
proof.
  move=> hkey.
  transitivity HonestTranscriptLoop.run
    (={arg} ==> ={res})
    (arg{1}=(pk0,sk0) /\ arg{2}=pk0 ==> ={res}).
  - by move=> &1 &2 [-> ->]; exists (pk0,sk0).
  - by move=> &1 &m &2 -> ->.
  - proc; while (={pk,sk,ot}).
    + call direct_honest_trial; auto.
    auto.
  exact (honest_simulated_loop pk0 sk0 hkey).
qed.

lemma accepted_simulated_loop pk0 sk0 : (pk0,sk0) \in SD.keygen =>
  equiv [AcceptedTranscript.run ~ SimTranscriptLoop.run :
    arg{1}=sk0 /\ arg{2}=pk0 ==> ={res}].
proof.
  move=> hkey.
  transitivity DirectTranscriptLoop.run
    (arg{1}=sk0 /\ arg{2}=(pk0,sk0) ==> ={res})
    (arg{1}=(pk0,sk0) /\ arg{2}=pk0 ==> ={res}).
  - by move=> &1 &2 [-> ->]; exists (pk0,sk0).
  - by move=> &1 &m &2 -> ->.
  - conseq accepted_direct_loop; progress.
  exact (direct_simulated_loop pk0 sk0 hkey).
qed.

op accepted_distribution (sk : SD.SK) =
  dcond (SD.commit sk `*` dC tau) (predC (trial_reject sk)).

lemma accepted_distribution_ll sk : SD.check sk =>
  is_lossless (accepted_distribution sk).
proof.
  move=> hsk; rewrite /accepted_distribution.
  apply dcond_ll.
  have ha := acceptance_probability sk hsk.
  have hp := rejection_range.
  rewrite /predC /trial_reject.
  move: ha hp; clear.
  move: p_rej (mu (SD.commit sk `*` dC tau)
    (fun x : (high list*vector)*Rq => SD.respond sk x.`2 x.`1.`2 <> None)) => p u.
  smt().
qed.

module FailedLog = {
  proc run(sk : SD.SK) = {
    var b,x,log;
    log <- [];
    b <$ DBool.Biased.dbiased (mu (SD.commit sk `*` dC tau) (trial_reject sk));
    while (b) {
      x <$ dcond (SD.commit sk `*` dC tau) (trial_reject sk);
      log <- rcons log x;
      b <$ DBool.Biased.dbiased (mu (SD.commit sk `*` dC tau) (trial_reject sk));
    }
    return log;
  }
}.

module SeparateTrials = {
  proc run(sk : SD.SK) = {
    var log,x;
    log <@ FailedLog.run(sk);
    x <$ accepted_distribution sk;
    return (log,x);
  }
}.

lemma logged_trials_separate : equiv
  [LoggedTrials(SingleTrial).run ~ SeparateTrials.run :
    ={arg} /\ SD.check arg{1} ==> ={res}].
proof.
  transitivity FactoredTrials.run
    (={arg} /\ SD.check arg{1} ==> ={res})
    (={arg} ==> ={res}).
  - by move=> &1 &2 [<- hc]; exists arg{1}.
  - by move=> &1 &m &2 -> ->.
  - exact logged_trials_factorization.
  proc; inline FailedLog.run; wp; rnd; wp.
  while (={sk,b} /\ sk0{2}=sk{1} /\ log{1}=log0{2});
    auto => />; try by rewrite /accepted_distribution.
qed.

lemma failed_log_projection : equiv
  [FailedLog.run ~ LoggedTrials(SingleTrial).run :
    ={arg} /\ SD.check arg{1} ==> res{1}=res{2}.`1].
proof.
  transitivity SeparateTrials.run
    (={arg} /\ SD.check arg{1} ==> res{1}=res{2}.`1)
    (={arg} /\ SD.check arg{1} ==> ={res}).
  - by move=> &1 &2 [<- hc]; exists arg{1}.
  - by move=> &1 &m &2 -> ->.
  - proc; inline FailedLog.run; wp; rnd{2}; wp.
    while (={sk,b} /\ sk0{2}=sk{1} /\ log{1}=log0{2} /\ SD.check sk{1}); auto.
    move=> &1 &2 [-> hc].
    have := accepted_distribution_ll sk{2} hc; progress.
  symmetry; conseq logged_trials_separate; progress.
qed.

module FailedBatch = {
  proc run(sk : SD.SK, n : int) = {
    var i,logs,ls;
    i <- 0; logs <- [];
    while (i < n) {
      ls <@ FailedLog.run(sk);
      logs <- rcons logs ls;
      i <- i+1;
    }
    return logs;
  }
}.

lemma failed_batch_projection : equiv
  [FailedBatch.run ~ BatchLogs.run :
    ={arg} /\ SD.check arg{1}.`1 ==> ={res}].
proof.
  proc; while (={sk,n,i,logs} /\ SD.check sk{1}).
  - wp; call failed_log_projection; auto.
  auto.
qed.

op program_trials (table : (high list*M,Rq) FMap.fmap) (msg : M)
  (xs : ((high list*vector)*Rq) list) =
  foldl (fun t (x : (high list*vector)*Rq) =>
    FMap."_.[_<-_]" t (x.`1.`1,msg) x.`2) table xs.

lemma program_trials_rcons table msg xs x :
  program_trials table msg (rcons xs x) =
  FMap."_.[_<-_]" (program_trials table msg xs) (x.`1.`1,msg) x.`2.
proof. by rewrite /program_trials foldl_rcons. qed.

module ProgramTranscript = {
  proc run(sk : SD.SK, msg : M, table : (high list*M,Rq) FMap.fmap) = {
    var x,ot;
    x <- witness; ot <- None;
    while (ot = None) {
      x <$ SD.commit sk `*` dC tau;
      ot <- trial_transcript sk x;
      table <- FMap."_.[_<-_]" table (x.`1.`1,msg) x.`2;
    }
    return (table,oget ot);
  }
}.

module LogTranscript = {
  proc run(sk : SD.SK, msg : M, table : (high list*M,Rq) FMap.fmap) = {
    var ls,x;
    (ls,x) <@ LoggedTrials(SingleTrial).run(sk);
    table <- program_trials table msg (rcons ls x);
    return (table,oget (trial_transcript sk x));
  }
}.

lemma program_transcript_log table0 : equiv
  [ProgramTranscript.run ~ LogTranscript.run :
    ={arg} /\ arg{1}.`3=table0 ==> ={res}].
proof.
(* COMPLETE THIS *)
  proc; inline LoggedTrials(SingleTrial).run SingleTrial.draw.
  unroll{1} 3; rcondt{1} 3; first by auto.
  wp.
  while (={sk,msg} /\ sk0{2}=sk{2} /\ table{2}=table0 /\
    table{1}=program_trials table0 msg{2} (rcons log{2} x0{2}) /\
    ot{1}=trial_transcript sk{2} x0{2}).
  - wp; rnd; auto.
  move=> &1 &2 H.
  have hsk : sk{1} = sk{2} by smt().
  have hmsg : msg{1} = msg{2} by smt().
  have hsk0 : sk0{2} = sk{2} by smt().
  have ht1 : table{1} = program_trials table0 msg{2} (rcons log{2} x0{2}) by smt().
  rewrite hsk hmsg hsk0 ht1.
  split.
  by move=> x hx.
  move=> _ x hx.
  rewrite program_trials_rcons trial_transcript_none.
  rewrite !program_trials_rcons.
  smt().
  wp; rnd; wp; auto.
  move=> &1 &2 H.
  have hsk : sk{1} = sk{2} by smt().
  have hmsg : msg{1} = msg{2} by smt().
  have ht1 : table{1} = table0 by smt().
  have ht2 : table{2} = table0 by smt().
  rewrite hsk hmsg ht1 ht2.
  split.
  by move=> x hx.
  move=> _ x hx.
  rewrite trial_transcript_none /program_trials /=.
  smt().
qed.

module QueueFill = {
  proc run(sk : SD.SK, n : int,
    queue : ((high list*vector)*Rq) list list,
    all : ((high list*vector)*Rq) list list) = {
    var ls;
    while (size queue < n) {
      ls <@ FailedLog.run(sk);
      queue <- rcons queue ls;
      all <- rcons all ls;
    }
    return (queue,all);
  }
}.

module QueueConsume = {
  proc take_eager(sk : SD.SK, n : int,
    queue : ((high list*vector)*Rq) list list,
    all : ((high list*vector)*Rq) list list) = {
    var ls;
    ls <- [];
    if (0 < n) {
      ls <- head [] queue;
      queue <- behead queue;
      n <- n-1;
    }
    return (n,queue,all,ls);
  }
  proc take_lazy(sk : SD.SK, n : int,
    queue : ((high list*vector)*Rq) list list,
    all : ((high list*vector)*Rq) list list) = {
    var ls;
    ls <- [];
    if (0 < n) {
      if (queue = []) {
        ls <@ FailedLog.run(sk);
        all <- rcons all ls;
      } else {
        ls <- head [] queue;
        queue <- behead queue;
      }
      n <- n-1;
    }
    return (n,queue,all,ls);
  }
}.

module FilledConsume = {
  proc run(sk : SD.SK, n : int,
    queue : ((high list*vector)*Rq) list list,
    all : ((high list*vector)*Rq) list list) = {
    var ls;
    (queue,all) <@ QueueFill.run(sk,n,queue,all);
    (n,queue,all,ls) <@ QueueConsume.take_eager(sk,n,queue,all);
    return (n,queue,all,ls);
  }
}.

module ConsumedFill = {
  proc run(sk : SD.SK, n : int,
    queue : ((high list*vector)*Rq) list list,
    all : ((high list*vector)*Rq) list list) = {
    var ls;
    (n,queue,all,ls) <@ QueueConsume.take_lazy(sk,n,queue,all);
    (queue,all) <@ QueueFill.run(sk,n,queue,all);
    return (n,queue,all,ls);
  }
}.

lemma queue_fill_consume : equiv
  [FilledConsume.run ~ ConsumedFill.run : ={arg} ==> ={res}].
proof.
(* COMPLETE THIS *)
  proc; inline QueueFill.run QueueConsume.take_eager QueueConsume.take_lazy.
  sp.
  case (!(0 < n{1})).
  - rcondf{1} 1.
  + auto; smt(List.size_ge0).
  rcondf{2} 1; first by auto.
  sp.
  rcondf{2} 1.
  + auto; smt(List.size_ge0).
  auto; smt().
  case (queue{1} = []).
  rcondt{2} 1; first auto; smt().
  rcondt{2} 1; first auto; smt().
  unroll{1} 1; rcondt{1} 1; first auto; smt().
  seq 1 1 : (={ls0, all0} /\ queue0{1} = [] /\ queue0{2} = [] /\ sk0{1} = sk{2} /\ n0{1} = n{1} /\ n0{2} = n{1} /\ 0 < n{1}).
  call (_ : true); auto.
  sim.
  sp.
  wp; while (queue0{1} = ls{2} :: queue1{2} /\ all0{1} = all1{2} /\ sk0{1} = sk1{2} /\ n0{1} = n{1} /\ n1{2} = n{2} /\ n{1} = n{2} + 1 /\ 0 < n{1}).
  wp; call (_ : true); first sim.
  auto; smt().
  auto; smt().
  rcondt{2} 1; first auto; smt().
  rcondf{2} 1; first auto; smt().
  sp; wp; while (queue0{1} = ls{2} :: queue1{2} /\ all0{1} = all1{2} /\ sk0{1} = sk1{2} /\ n0{1} = n{1} /\ n1{2} = n{2} /\ n{1} = n{2} + 1 /\ 0 < n{1}).
  wp; call (_ : true); first sim.
  auto; smt().
  auto; smt().
qed.

module type KeyedExperiment = {
  proc run(ks : SD.PK*SD.SK) : bool
}.

module AverageExperiment (G : KeyedExperiment) = {
  proc main() = {
    var ks,b;
    ks <$ SD.keygen;
    b <@ G.run(ks);
    return (ks,b);
  }
}.

lemma key_component_probability (G <: KeyedExperiment) &m ks0 :
  Pr[AverageExperiment(G).main() @ &m : res.`2 /\ res.`1=ks0] =
  mu1 SD.keygen ks0 * Pr[G.run(ks0) @ &m : res].
proof.
  byphoare (_ : (glob G)=(glob G){m} ==> res.`2 /\ res.`1=ks0) => //.
  pose pr := Pr[G.run(ks0) @ &m : res].
  proc.
  seq 1 : (ks=ks0) (mu1 SD.keygen ks0) pr 1%r 0%r
    ((glob G)=(glob G){m}) => //.
  - by rnd.
  - by rnd; auto => />; rewrite pred1E.
  - call (_ : (glob G)=(glob G){m} /\ arg=ks0 ==> res) => //.
    rewrite /pr; bypr => /> &0 eqGlob.
    by byequiv (_ : ={glob G,arg} ==> ={res,glob G}) => //; proc true.
  by hoare; call (_ : true); auto => /#.
qed.

lemma key_probability_sum (G <: KeyedExperiment) &m
  (xs : (SD.PK*SD.SK) list) : uniq xs =>
  Pr[AverageExperiment(G).main() @ &m : res.`2 /\ res.`1 \in xs] =
  StdBigop.Bigreal.BRA.big predT
    (fun ks => mu1 SD.keygen ks * Pr[G.run(ks) @ &m : res]) xs.
proof.
(* COMPLETE THIS *)
  elim: xs => [|x xs ih] /=.
  - rewrite StdBigop.Bigreal.BRA.big_nil.
  by rewrite Pr[mu_false].
  move=> [hx hu].
  rewrite StdBigop.Bigreal.BRA.big_cons /=.
  have -> : Pr[AverageExperiment(G).main() @ &m : res.`2 /\ (res.`1 = x \/ (res.`1 \in xs))] = Pr[AverageExperiment(G).main() @ &m : (res.`2 /\ res.`1 = x) \/ (res.`2 /\ res.`1 \in xs)].
  rewrite Pr[mu_eq].
  by move=> &hr; case: (res{hr}.`2).
  trivial.
  rewrite Pr[mu_disjoint].
  move=> &hr; case: (res{hr}.`1 = x) => heq /=.
  by rewrite heq hx /=.
  trivial.
  by rewrite (key_component_probability G &m x) (ih hu) /predT /=.
qed.

lemma key_average_probability (G <: KeyedExperiment) &m :
  Pr[AverageExperiment(G).main() @ &m : res.`2] =
  E SD.keygen (fun ks => Pr[G.run(ks) @ &m : res]).
proof.
  have hs : Pr[AverageExperiment(G).main() @ &m : res.`2] =
    Pr[AverageExperiment(G).main() @ &m :
      res.`2 /\ res.`1 \in to_seq (support SD.keygen)].
  - byequiv (_ : ={glob G} ==> ={res} /\ res{1}.`1 \in SD.keygen) => //.
    + proc; call (_ : true); auto.
    move=> &1 &2 [hr hk]; rewrite hr mem_to_seq; first exact SD.keygen_finite.
    by rewrite -hr hk.
  rewrite hs (key_probability_sum G &m _ (uniq_to_seq _))
    (fin_expE SD.keygen _ SD.keygen_finite).
  apply StdBigop.Bigreal.BRA.eq_big_seq => ks hks.
  rewrite /=; ring.
qed.

module GenericBudget (B : Adv_EFCMA_RO) (H0 : SD.FSaG.DSS.Hash)
  (O0 : SD.FSaG.DSS.DS.Stateless.SOracle_CMA) = {
  proc run(pk : SD.PK) = {
    var r;
    SD.CMAtoKOA.CountH.qh <- 0; SD.CMAtoKOA.CountS.qs <- 0;
    r <@ SD.CG.RedFSaG(RedS(B),SD.CMAtoKOA.CountH(H0),SD.CMAtoKOA.CountS(O0)).forge(pk);
    return r;
  }
}.

module GhostBudget (B : Adv_EFCMA_RO) (H0 : SD.FSaG.DSS.Hash)
  (O0 : SD.FSaG.DSS.DS.Stateless.SOracle_CMA) = {
  proc run(pk : SD.PK) = {
    var msg,sig,c,z,w;
    SD.CMAtoKOA.CountH.qh <- 0; SD.CMAtoKOA.CountS.qs <- 0;
    SD.CountH.qh <- 0; SD.CountS.qs <- 0;
    (msg,sig) <@ B(SD.CountH(SD.CMAtoKOA.CountH(H0)),
      SD.CountS(SD.CG.OCR(SD.CMAtoKOA.CountH(H0),SD.CMAtoKOA.CountS(O0)))).forge
      (pk.`1,base2highbitsV pk.`2);
    (c,z) <- sig;
    w <- SD.recover pk c z;
    return (msg,(w,z));
  }
}.

module UnloggedSign (O : SD.CMAtoKOA.R1.Oracle) = {
  proc sign(msg : M) = {
    var w,c,z;
    (w,c,z) <@ O.sign(msg);
    return (w,z);
  }
}.

lemma generic_budget_same
  (O' <: SD.CMAtoKOA.R1.Oracle {-A,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  equiv [GenericBudget(A,ROMHash(O'),UnloggedSign(O')).run ~
    GhostBudget(A,ROMHash(O'),UnloggedSign(O')).run :
    ={arg,glob A,glob O'} ==>
    ={res,SD.CMAtoKOA.CountH.qh,SD.CMAtoKOA.CountS.qs}].
proof.
  proc; inline *; wp.
  call (_ : ={glob O',SD.CMAtoKOA.CountH.qh,SD.CMAtoKOA.CountS.qs}).
  - proc; inline *; wp; call (_ : true); wp; call (_ : true); auto.
  - proc; inline *; wp; call (_ : true); auto.
  auto.
qed.

lemma ghost_game_budget
  (H' <: SD.FSaG.DSS.Hash {-A,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS})
  (O' <: SD.FSaG.DSS.DS.Stateless.SOracle_CMA {-A,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [GhostBudget(A,H',O').run : true ==>
    SD.CMAtoKOA.CountH.qh <= qH+qS /\ SD.CMAtoKOA.CountS.qs <= qS].
proof.
  proc; wp; call (ghost_adversary_budget H' O'); inline *; auto.
qed.

lemma generic_game_budget
  (O' <: SD.CMAtoKOA.R1.Oracle {-A,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [GenericBudget(A,ROMHash(O'),UnloggedSign(O')).run : true ==>
    SD.CMAtoKOA.CountH.qh <= qH+qS /\ SD.CMAtoKOA.CountS.qs <= qS].
proof.
  conseq (generic_budget_same O') (ghost_game_budget (ROMHash(O')) (UnloggedSign(O'))); smt().
qed.

module type GatedOracle = {
  include SD.CMAtoKOA.R1.Oracle
  proc excess_h(w : high list, msg : M) : Rq
  proc excess_sign(msg : M) : high list*Rq*SD.response_t
}.

module CountedGate (O : GatedOracle) = {
  proc h(w : high list, msg : M) = {
    var c;
    SD.CMAtoKOA.CountH.qh <- SD.CMAtoKOA.CountH.qh+1;
    if (SD.CMAtoKOA.CountH.qh <= external_budget) {
      c <@ O.h(w,msg);
    } else {
      c <@ O.excess_h(w,msg);
    }
    return c;
  }
  proc sign(msg : M) = {
    var sig;
    SD.CMAtoKOA.CountS.qs <- SD.CMAtoKOA.CountS.qs+1;
    if (SD.CMAtoKOA.CountS.qs <= qS) {
      sig <@ O.sign(msg);
    } else {
      sig <@ O.excess_sign(msg);
    }
    return sig;
  }
}.

lemma primitive_counter_balance
  (O <: GatedOracle {-A,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [A(SD.CountH(ROMHash(CountedGate(O))),
    SD.CountS(SD.CG.OCR(ROMHash(CountedGate(O)),
      UnloggedSign(CountedGate(O))))).forge :
    SD.CMAtoKOA.CountH.qh=SD.CountH.qh+SD.CountS.qs /\
    SD.CMAtoKOA.CountS.qs=SD.CountS.qs ==>
    SD.CMAtoKOA.CountH.qh=SD.CountH.qh+SD.CountS.qs /\
    SD.CMAtoKOA.CountS.qs=SD.CountS.qs].
proof.
  proc (SD.CMAtoKOA.CountH.qh=SD.CountH.qh+SD.CountS.qs /\
    SD.CMAtoKOA.CountS.qs=SD.CountS.qs) => //.
  - proc; inline *; sp.
    seq 1 : (SD.CMAtoKOA.CountH.qh=SD.CountH.qh+SD.CountS.qs-1 /\
      SD.CMAtoKOA.CountS.qs=SD.CountS.qs).
    + if; wp; call (_ : true); auto; smt().
    sp; if; wp; call (_ : true); auto; smt().
  - proc; inline *; sp; if; wp; call (_ : true); auto; smt().
qed.

module BareOracleBudget (B : Adv_EFCMA_RO) (O : SD.CMAtoKOA.R1.Oracle) = {
  proc run(pk : SD.PK) = {
    var r;
    r <@ SD.CG.RedFSaG(RedS(B),ROMHash(O),UnloggedSign(O)).forge(pk);
    return r;
  }
}.

module OriginalOracleBudget (B : Adv_EFCMA_RO) (O : SD.CMAtoKOA.R1.Oracle) = {
  proc run(pk : SD.PK) = {
    var msg,sig,c,z,w;
    SD.CountH.qh <- 0; SD.CountS.qs <- 0;
    (msg,sig) <@ B(SD.CountH(ROMHash(O)),
      SD.CountS(SD.CG.OCR(ROMHash(O),UnloggedSign(O)))).forge
      (pk.`1,base2highbitsV pk.`2);
    (c,z) <- sig;
    w <- SD.recover pk c z;
    return (msg,(w,z));
  }
}.

lemma bare_original_same
  (O <: SD.CMAtoKOA.R1.Oracle {-A,-SD.CountH,-SD.CountS}) :
  equiv [BareOracleBudget(A,O).run ~ OriginalOracleBudget(A,O).run :
    ={arg,glob A,glob O} ==> ={res,glob O}].
proof.
  proc; inline *; wp; call (_ : ={glob O}).
  - proc; inline *; wp; call (_ : true); wp; call (_ : true); auto.
  - proc; inline *; wp; call (_ : true); auto.
  auto.
qed.

lemma primitive_original_budget
  (O <: GatedOracle {-A,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [OriginalOracleBudget(A,CountedGate(O)).run :
    SD.CMAtoKOA.CountH.qh=0 /\ SD.CMAtoKOA.CountS.qs=0 ==>
    SD.CMAtoKOA.CountH.qh<=qH+qS /\ SD.CMAtoKOA.CountS.qs<=qS].
proof.
  proc; wp.
  call (_ : SD.CountH.qh=0 /\ SD.CountS.qs=0 /\
    SD.CMAtoKOA.CountH.qh=0 /\ SD.CMAtoKOA.CountS.qs=0 ==>
    SD.CMAtoKOA.CountH.qh<=qH+qS /\ SD.CMAtoKOA.CountS.qs<=qS).
  - conseq (A_bound (ROMHash(CountedGate(O)))
      (SD.CG.OCR(ROMHash(CountedGate(O)),UnloggedSign(CountedGate(O)))))
      (primitive_counter_balance O); smt().
  auto.
qed.

lemma gate_bare_budget
  (O <: GatedOracle {-A,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [BareOracleBudget(A,CountedGate(O)).run :
    SD.CMAtoKOA.CountH.qh=0 /\ SD.CMAtoKOA.CountS.qs=0 ==>
    SD.CMAtoKOA.CountH.qh<=qH+qS /\ SD.CMAtoKOA.CountS.qs<=qS].
proof.
  conseq (bare_original_same (CountedGate(O)))
    (primitive_original_budget O); smt().
qed.

op response_transcript (x : (high list*vector)*Rq) (oz : SD.response_t option) =
  omap (fun z => (x.`1.`1,x.`2,z)) oz.

lemma response_transcript_none x oz :
  (response_transcript x oz=None)=(oz=None).
proof. by rewrite /response_transcript; case oz. qed.

lemma oget_response_transcript x oz : oz<>None =>
  oget (response_transcript x oz)=(x.`1.`1,x.`2,oget oz).
proof. by rewrite /response_transcript; case oz. qed.

module ResponseProgram = {
  proc run(sk : SD.SK, msg : M, table : (high list*M,Rq) FMap.fmap) = {
    var x,oz;
    x <- witness; oz <- None;
    while (oz=None) {
      x <$ SD.commit sk `*` dC tau;
      oz <- SD.respond sk x.`2 x.`1.`2;
      table <- FMap."_.[_<-_]" table (x.`1.`1,msg) x.`2;
    }
    return (table,(x.`1.`1,x.`2,oget oz));
  }
}.

lemma response_program_transcript : equiv
  [ResponseProgram.run ~ ProgramTranscript.run : ={arg} ==> ={res}].
proof.
(* COMPLETE THIS *)
  proc.
  while (={sk,msg,table,x} /\ ot{2}=response_transcript x{1} oz{1}).
  - wp; rnd; auto.
  move=> &1 &2 h.
  have hsk : sk{1} = sk{2} by smt().
  have hmsg : msg{1} = msg{2} by smt().
  have htable : table{1} = table{2} by smt().
  rewrite -hsk -hmsg -htable /=.
  move=> xL hxL.
  by rewrite hxL trial_transcript_none /trial_reject /trial_transcript /response_transcript.
  wp; auto.
  smt(response_transcript_none oget_response_transcript).
qed.

lemma failed_log_lossless sk0 : SD.check sk0 =>
  phoare [FailedLog.run : arg=sk0 ==> true] = 1%r.
proof.
  move=> hsk.
  conseq failed_log_projection (logged_trials_lossless sk0 hsk); smt().
qed.

lemma failed_batch_lossless sk0 n0 : SD.check sk0 =>
  phoare [FailedBatch.run : arg=(sk0,n0) ==> true] = 1%r.
proof.
  move=> hsk.
  conseq failed_batch_projection (batch_logs_lossless sk0 n0 hsk); smt().
qed.

lemma queue_fill_lossless sk0 : SD.check sk0 =>
  phoare [QueueFill.run : sk=sk0 ==> true] = 1%r.
proof.
  move=> hsk; proc.
  while (sk=sk0) (n-size queue).
  - move=> z; wp; call (failed_log_lossless sk0 hsk).
    auto; smt(List.size_rcons).
  auto; smt().
qed.

local lemma programmed_hash_lossless : islossless Programmed.h.
proof.
  proc; islossless.
qed.

local lemma rom_hash_key_ll sk0 :
  phoare [ROMHash(Programmed).get : Programmed.sk = sk0 ==>
    Programmed.sk = sk0] = 1%r.
proof.
  proc; call (_ : Programmed.sk = sk0 ==> Programmed.sk = sk0).
  - by conseq programmed_hash_lossless.
  by auto.
qed.

local lemma rom_sign_key_ll sk0 : SD.check sk0 =>
  phoare [ROMSign(Programmed).sign : Programmed.sk = sk0 ==>
    Programmed.sk = sk0] = 1%r.
proof.
  move=> hsk; proc; wp.
  call (_ : Programmed.sk = sk0 ==> Programmed.sk = sk0).
  - by conseq (programmed_sign_lossless sk0 hsk).
  by auto.
qed.

local lemma original_programmed_ll sk0 : SD.check sk0 =>
  phoare [A(ROMHash(Programmed),
    SD.CG.OCR(ROMHash(Programmed),ROMSign(Programmed))).forge :
    Programmed.sk = sk0 ==> Programmed.sk = sk0] = 1%r.
proof.
  move=> hsk; proc (Programmed.sk = sk0) => //.
  - move=> H' O' hs hh; exact (A_ll O' H' hs hh).
  - proc; wp; call (rom_hash_key_ll sk0); wp; call (rom_sign_key_ll sk0 hsk); auto.
  - exact (rom_hash_key_ll sk0).
qed.

lemma conditioned_mass_identity ['a] (d : 'a distr) good f :
  E d (fun x => if good x then f x else 0%r) =
    mu d good * E (dcond d good) f.
proof.
  rewrite exp_dcond /Ec.
  case (mu d good = 0%r) => hm.
  - rewrite hm /=; apply exp_eq0 => x hx.
    have hg := eq0_mu d good hm x hx.
    change ((if good x then f x else 0%r) = 0%r).
    by rewrite ifF.
  move: hm; clear; move: (mu d good)
    (E d (fun x => if good x then f x else 0%r)) => m e hm.
  field; smt().
qed.

lemma good_key_entropy :
  E SD.keygen (fun ks : SD.PK*SD.SK =>
    if SD.check ks.`2 then p_max (dfst (SD.commit ks.`2)) else 0%r) <= eps_comm.
proof.
  rewrite conditioned_mass_identity.
  have he := SD.check_entropy.
  have he0 : 0%r <= E (dcond SD.keygen (fun ks : SD.PK*SD.SK => SD.check ks.`2))
      (fun ks : SD.PK*SD.SK => p_max (dfst (SD.commit ks.`2))).
  - apply exp_ge0 => ks hks; apply ge0_pmax.
  have hp := mu_bounded SD.keygen (fun ks : SD.PK*SD.SK => SD.check ks.`2).
  move: he he0 hp; clear.
  move: (mu SD.keygen (fun ks : SD.PK*SD.SK => SD.check ks.`2))
    (E (dcond SD.keygen (fun ks : SD.PK*SD.SK => SD.check ks.`2))
      (fun ks : SD.PK*SD.SK => p_max (dfst (SD.commit ks.`2)))) eps_comm => p e eps.
  smt().
qed.

lemma average_security_bound (f g : SD.PK*SD.SK -> real) C :
  0%r <= C =>
  (forall ks, 0%r <= f ks <= 1%r /\ 0%r <= g ks) =>
  (forall ks, ks \in SD.keygen => SD.check ks.`2 =>
    f ks <= g ks + C * p_max (dfst (SD.commit ks.`2))) =>
  E SD.keygen f <= E SD.keygen g + C * eps_comm + delta_.
proof.
  move=> hC hfg hgood.
  have hf : forall (h : SD.PK*SD.SK -> real), hasE SD.keygen h.
  - move=> h; apply hasE_finite; exact SD.keygen_finite.
  pose e := fun ks : SD.PK*SD.SK =>
    if SD.check ks.`2 then p_max (dfst (SD.commit ks.`2)) else 0%r.
  pose b := fun ks : SD.PK*SD.SK => if !SD.check ks.`2 then 1%r else 0%r.
  have hbnd : E SD.keygen f <= E SD.keygen (fun ks => g ks + (C * e ks + b ks)).
  - apply in_ler_exp; first exact (hf f).
    + apply hf.
    move=> ks hks; have hg := hfg ks.
    rewrite /e /b; case (SD.check ks.`2) => hc /=.
    + have hh := hgood ks hks hc; smt().
    have hno : SD.check ks.`2 = false by smt().
    rewrite hno /=.
    move: hg; clear; move: (f ks) (g ks) => a b; smt().
  have he : E SD.keygen e <= eps_comm by exact good_key_entropy.
  have hb := SD.check_most.
  move: hbnd; rewrite
    (expD SD.keygen g (fun ks => C * e ks + b ks) (hf g) (hf _))
    (expD SD.keygen (fun ks => C * e ks) b (hf _) (hf b))
    expZ /b expC_cond /=.
  move=> hbnd.
  move: he hb hbnd hC; clear.
  move: (E SD.keygen f) (E SD.keygen g) (E SD.keygen e)
    (mu SD.keygen (fun ks : SD.PK*SD.SK => !SD.check ks.`2)) C eps_comm delta_
    => pf pg ep pb c eps dlt; smt().
qed.

local lemma programmed_adversary_stopped_same
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign}) :
  equiv [ROMAdversary(B,Programmed).distinguish ~
    ROMAdversary(B,Monitored(StopCollision)).distinguish :
    ={arg,glob B,glob Programmed} ==> ={res,glob Programmed}].
proof.
  proc; wp.
  call (_ : ={arg,glob Programmed} ==> ={res,glob Programmed}).
  - by proc; sim.
  wp; call (_ : ={glob Programmed,ROMSign.qs}).
  - proc; wp; call stop_sign_same; auto.
  - by proc; sim.
  auto.
qed.

local lemma programmed_stopped_same
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign}) :
  equiv [ProgrammedGame(B).main ~ MonitoredGame(B,StopCollision).main :
    ={arg,glob B} ==> ={res,glob Programmed}].
proof.
  proc; call (programmed_adversary_stopped_same B).
  inline Programmed.init; auto.
qed.

local lemma raw_stop_nonbad (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed}) pk sk &m :
  Pr[MonitoredGame(B,RawCollision).main(pk,sk) @ &m : !Programmed.bad] =
  Pr[MonitoredGame(B,StopCollision).main(pk,sk) @ &m : !Programmed.bad].
proof. byupto. qed.

local lemma independent_stop_nonbad (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed}) pk sk &m :
  Pr[MonitoredGame(B,IndependentCollision).main(pk,sk) @ &m : !Programmed.bad] =
  Pr[MonitoredGame(B,StopCollision).main(pk,sk) @ &m : !Programmed.bad].
proof. byupto. qed.

local lemma monitored_stop_bad_bound
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign}) pk sk &m :
  SD.check sk =>
  Pr[MonitoredGame(B,StopCollision).main(pk,sk) @ &m : Programmed.bad] <=
    trial_cost (p_max (dfst (SD.commit sk))) qS 0.
proof.
  move=> hsk.
  have he : Pr[MonitoredGame(B,StopCollision).main(pk,sk) @ &m : Programmed.bad] =
    Pr[ProgrammedGame(B).main(pk,sk) @ &m : Programmed.bad].
  - rewrite eq_sym; byequiv (programmed_stopped_same B) => //.
  rewrite he; exact (programmed_game_bad B pk sk &m hsk).
qed.

local lemma converted_programmed_ll sk0 : SD.check sk0 =>
  phoare [SD.CG.RedFSaG(RedS(A),ROMHash(Programmed),ROMSign(Programmed)).forge :
    Programmed.sk = sk0 ==> Programmed.sk = sk0] = 1%r.
proof.
  move=> hsk; proc; inline *; wp; call (original_programmed_ll sk0 hsk); auto.
qed.

local lemma rom_fixed_ll sk0 : SD.check sk0 =>
  phoare [ROMAdversary(SD.CG.RedFSaG(RedS(A)),Programmed).distinguish :
    Programmed.sk = sk0 ==> true] = 1%r.
proof.
  move=> hsk; proc; wp.
  call (_ : Programmed.sk = sk0 ==> Programmed.sk = sk0).
  - by conseq programmed_hash_lossless.
  wp; call (converted_programmed_ll sk0 hsk); auto.
qed.

local lemma programmed_fixed_game_ll pk sk0 &m : SD.check sk0 =>
  Pr[ProgrammedGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk0) @ &m : true] = 1%r.
proof.
  move=> hsk; byphoare (_ : arg = (pk,sk0) ==> true) => //.
  proc; call (rom_fixed_ll sk0 hsk); inline Programmed.init; auto.
qed.

local lemma stopped_fixed_game_ll pk sk0 &m : SD.check sk0 =>
  Pr[MonitoredGame(SD.CG.RedFSaG(RedS(A)),StopCollision).main(pk,sk0) @ &m : true] = 1%r.
proof.
  move=> hsk.
  have he : Pr[MonitoredGame(SD.CG.RedFSaG(RedS(A)),StopCollision).main(pk,sk0) @ &m : true] =
    Pr[ProgrammedGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk0) @ &m : true].
  - rewrite eq_sym; byequiv (programmed_stopped_same (SD.CG.RedFSaG(RedS(A)))) => //.
  rewrite he; exact (programmed_fixed_game_ll pk sk0 &m hsk).
qed.

local lemma raw_independent_hop
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign}) pk sk &m :
  SD.check sk =>
  Pr[MonitoredGame(B,StopCollision).main(pk,sk) @ &m : true] = 1%r =>
  Pr[MonitoredGame(B,RawCollision).main(pk,sk) @ &m : res] <=
  Pr[MonitoredGame(B,IndependentCollision).main(pk,sk) @ &m : res] +
    trial_cost (p_max (dfst (SD.commit sk))) qS 0.
proof.
  move=> hsk hll.
  have hb := monitored_stop_bad_bound B pk sk &m hsk.
  have hr := raw_stop_upto B pk sk &m.
  have hi := independent_stop_upto B pk sk &m.
  have hn := raw_stop_nonbad B pk sk &m.
  move: hn; rewrite Pr[mu_not] Pr[mu_not] hll; move=> hn.
  have ht : Pr[MonitoredGame(B,RawCollision).main(pk,sk) @ &m : true] <= 1%r.
  - by rewrite Pr[mu_le1].
  have hs : Pr[MonitoredGame(B,RawCollision).main(pk,sk) @ &m : res] =
    Pr[MonitoredGame(B,RawCollision).main(pk,sk) @ &m : res /\ !Programmed.bad] +
    Pr[MonitoredGame(B,RawCollision).main(pk,sk) @ &m : res /\ Programmed.bad].
  - by rewrite Pr[mu_split !Programmed.bad] /=.
  have hp : Pr[MonitoredGame(B,RawCollision).main(pk,sk) @ &m : res /\ Programmed.bad] <=
    Pr[MonitoredGame(B,RawCollision).main(pk,sk) @ &m : Programmed.bad].
  - by rewrite Pr[mu_sub]; smt().
  have hq : Pr[MonitoredGame(B,IndependentCollision).main(pk,sk) @ &m : res /\ !Programmed.bad] <=
    Pr[MonitoredGame(B,IndependentCollision).main(pk,sk) @ &m : res].
  - by rewrite Pr[mu_sub]; smt().
  clear hsk hll; smt().
qed.

op rom_coefficient =
  2%r*qS%r*external_budget%r/(1%r-p_rej) +
  qS%r*(qS%r+1%r)/(2%r*(1%r-p_rej)^2).

lemma rom_coefficient_ge0 : 0%r <= rom_coefficient.
proof.
  have hp := rejection_range.
  have hs := qS_ge0; have hh := qH_ge0.
  rewrite /rom_coefficient /external_budget !fromintD /=.
  have hs' : 0%r <= qS%r by smt().
  have hh' : 0%r <= qH%r by smt().
  move: hp hs' hh'; clear; move: p_rej qS%r qH%r => p s h.
  smt(RealOrder.divr_ge0 RealOrder.mulr_ge0 RField.expr2).
qed.

lemma rom_cost_assembly e :
  trial_cost e qS 0 + qS%r*external_budget%r*e/(1%r-p_rej) =
  e*rom_coefficient.
proof.
  rewrite /trial_cost /rom_coefficient !fromintM !fromintD /=.
  ring.
qed.

lemma rom_final_cost :
  rom_coefficient * eps_comm =
  2%r*qS%r*(qH+qS+1)%r*eps_comm/(1%r-p_rej) +
  qS%r*eps_comm*(qS%r+1%r)/(2%r*(1%r-p_rej)^2).
proof. rewrite /rom_coefficient /external_budget; ring. qed.

local module AcceptedOnly = {
  include var Programmed [init,h]
  proc sign(msg : M) = {
    var w,c,z;
    w <- witness; c <- witness; z <- witness;
    if (countS < qS) {
      (w,c,z) <@ AcceptedTranscript.run(sk);
      table <- FMap."_.[_<-_]" table (w,msg) c;
      countS <- countS+1;
    }
    return (w,c,z);
  }
}.

local module SimulatedOnly = {
  var pk : SD.PK
  include var Programmed [h]
  proc init(pk0 : SD.PK, sk0 : SD.SK) = {
    pk <- pk0;
    Programmed.init(sk0);
  }
  proc sign(msg : M) = {
    var w,c,z;
    w <- witness; c <- witness; z <- witness;
    if (countS < qS) {
      (w,c,z) <@ SimTranscriptLoop.run(pk);
      table <- FMap."_.[_<-_]" table (w,msg) c;
      countS <- countS+1;
    }
    return (w,c,z);
  }
}.

local module AcceptedOnlyGame (B : SD.FSaG.DSS.Adv_EFCMA_RO) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r;
    Programmed.init(sk);
    r <@ ROMAdversary(B,AcceptedOnly).distinguish(pk);
    return r;
  }
}.

local module SimulatedOnlyGame (B : SD.FSaG.DSS.Adv_EFCMA_RO) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r;
    SimulatedOnly.init(pk,sk);
    r <@ ROMAdversary(B,SimulatedOnly).distinguish(pk);
    return r;
  }
}.

local lemma accepted_simulated_sign pk0 sk0 : (pk0,sk0) \in SD.keygen =>
  equiv [AcceptedOnly.sign ~ SimulatedOnly.sign :
    ={arg,glob Programmed} /\ Programmed.sk{1}=sk0 /\ SimulatedOnly.pk{2}=pk0 ==>
    ={res,glob Programmed}].
proof.
  move=> hkey; proc; sp; if; first by move=> &1 &2 />.
  - wp; call (accepted_simulated_loop pk0 sk0 hkey); auto.
  by auto.
qed.

local lemma accepted_simulated_adversary
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-SimulatedOnly,-ROMSign}) pk0 sk0 :
  (pk0,sk0) \in SD.keygen =>
  equiv [ROMAdversary(B,AcceptedOnly).distinguish ~
    ROMAdversary(B,SimulatedOnly).distinguish :
    ={arg,glob B,glob Programmed} /\ Programmed.sk{1}=sk0 /\ SimulatedOnly.pk{2}=pk0 ==>
    ={res}].
proof.
  move=> hkey; proc; wp.
  call (_ : ={arg,glob Programmed} ==> ={res,glob Programmed}).
  - by proc; sim.
  wp; call (_ : ={glob Programmed,ROMSign.qs} /\
    Programmed.sk{1}=sk0 /\ SimulatedOnly.pk{2}=pk0).
  - proc; wp; call (accepted_simulated_sign pk0 sk0 hkey); auto.
  - proc; inline *; sp; if; first by move=> &1 &2 />.
    + auto => />.
    by auto.
  auto.
qed.

local lemma accepted_simulated_game
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-SimulatedOnly,-ROMSign}) pk0 sk0 :
  (pk0,sk0) \in SD.keygen =>
  equiv [AcceptedOnlyGame(B).main ~ SimulatedOnlyGame(B).main :
    ={arg,glob B} /\ arg{1}=(pk0,sk0) ==> ={res}].
proof.
  move=> hkey; proc; call (accepted_simulated_adversary B pk0 sk0 hkey).
  inline SimulatedOnly.init Programmed.init; auto.
qed.

local module HiddenLogs = {
  var queue : ((high list*vector)*Rq) list list
  var all : ((high list*vector)*Rq) list list
  proc fill() = {
    (queue,all) <@ QueueFill.run(Programmed.sk,qS-Programmed.countS,queue,all);
  }
  proc take_eager() = {
    var n,ls;
    (n,queue,all,ls) <@ QueueConsume.take_eager
      (Programmed.sk,qS-Programmed.countS,queue,all);
    Programmed.countS <- qS-n;
    return ls;
  }
  proc take_lazy() = {
    var n,ls;
    (n,queue,all,ls) <@ QueueConsume.take_lazy
      (Programmed.sk,qS-Programmed.countS,queue,all);
    Programmed.countS <- qS-n;
    return ls;
  }
}.

local lemma eager_hidden_take :
  eager [HiddenLogs.fill();, HiddenLogs.take_eager ~ HiddenLogs.take_lazy,
    HiddenLogs.fill(); :
    ={glob HiddenLogs,Programmed.sk,Programmed.countS} ==>
    ={res,glob HiddenLogs,Programmed.sk,Programmed.countS}].
proof.
  eager proc; inline HiddenLogs.fill.
  transitivity* {1} {
    (n,HiddenLogs.queue,HiddenLogs.all,ls) <@ FilledConsume.run
      (Programmed.sk,qS-Programmed.countS,HiddenLogs.queue,HiddenLogs.all);
    Programmed.countS <- qS-n;
    result <- ls;
  }.
  - inline FilledConsume.run; wp.
    call (_ : true); first by sim.
    wp; call (_ : true); first by sim.
    by auto.
  transitivity* {2} {
    (n,HiddenLogs.queue,HiddenLogs.all,ls) <@ ConsumedFill.run
      (Programmed.sk,qS-Programmed.countS,HiddenLogs.queue,HiddenLogs.all);
    Programmed.countS <- qS-n;
    result <- ls;
  }.
  - wp; call queue_fill_consume; auto.
  inline ConsumedFill.run; wp.
  call (_ : true); first by sim.
  wp; call (_ : true); first by sim.
  auto => />; smt().
qed.

module type LogConsumer = {
  proc take() : ((high list*vector)*Rq) list
}.

local module EagerLogConsumer = { proc take = HiddenLogs.take_eager }.
local module LazyLogConsumer = { proc take = HiddenLogs.take_lazy }.

local module LoggedOracle (Take : LogConsumer) = {
  include var Programmed [h]
  proc sign(msg : M) = {
    var ls,x,sig;
    sig <- (witness,witness,oget None);
    if (countS < qS) {
      ls <@ Take.take();
      x <$ accepted_distribution sk;
      table <- program_trials table msg (rcons ls x);
      sig <- oget (trial_transcript sk x);
    }
    return sig;
  }
}.

local module LazyLoggedGame (B : SD.FSaG.DSS.Adv_EFCMA_RO) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r;
    Programmed.init(sk);
    HiddenLogs.queue <- []; HiddenLogs.all <- [];
    r <@ ROMAdversary(B,LoggedOracle(LazyLogConsumer)).distinguish(pk);
    HiddenLogs.fill();
    return r;
  }
}.

local module EagerLoggedGame (B : SD.FSaG.DSS.Adv_EFCMA_RO) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r;
    Programmed.init(sk);
    HiddenLogs.queue <- []; HiddenLogs.all <- [];
    HiddenLogs.fill();
    r <@ ROMAdversary(B,LoggedOracle(EagerLogConsumer)).distinguish(pk);
    return r;
  }
}.

module type HiddenHashPolicy = {
  proc choose(full : (high list*M,Rq) FMap.fmap,
    visible : (high list*M,Rq) FMap.fmap, key : high list*M, fresh : Rq) : Rq
}.

module FullHashPolicy = {
  proc choose(full : (high list*M,Rq) FMap.fmap,
    visible : (high list*M,Rq) FMap.fmap, key : high list*M, fresh : Rq) = {
    return if FMap.dom full key then oget (FMap."_.[_]" full key) else fresh;
  }
}.

module VisibleHashPolicy = {
  proc choose(full : (high list*M,Rq) FMap.fmap,
    visible : (high list*M,Rq) FMap.fmap, key : high list*M, fresh : Rq) = {
    return if FMap.dom visible key then oget (FMap."_.[_]" visible key) else fresh;
  }
}.

local module RejectMonitor = {
  var visible : (high list*M,Rq) FMap.fmap
  var seen : high list list
  var bad : bool
}.

op hidden_hit (w : high list) (logs : ((high list*vector)*Rq) list list) =
  has (fun x : (high list*vector)*Rq => x.`1.`1=w) (flatten logs).

op hidden_tables_match (full visible : (high list*M,Rq) FMap.fmap)
  (logs : ((high list*vector)*Rq) list list) =
  forall (key : high list*M), !hidden_hit key.`1 logs =>
    FMap."_.[_]" full key=FMap."_.[_]" visible key.

lemma hidden_program_preserves full visible logs msg ls x :
  hidden_tables_match full visible logs => ls \in logs =>
  hidden_tables_match (program_trials full msg (rcons ls x))
    (FMap."_.[_<-_]" visible (x.`1.`1,msg) x.`2) logs.
proof.
(* COMPLETE THIS *)
  move=> hmatch hls.
  rewrite /hidden_tables_match program_trials_rcons.
  move=> key hmiss.
  rewrite !FMap.get_setE.
  case ((x.`1.`1,msg)=key); first by smt().
  move=> hne; have hbase := hmatch key hmiss; move: hmiss; rewrite /hidden_hit => hmiss; have havoid : forall y, y \in ls => y.`1.`1 <> key.`1 by smt(hasP flattenP).
  have hfold : forall (ys : ((high list * vector) * Rq) list) (t : (high list * M, Rq) FMap.fmap), (forall y, y \in ys => y.`1.`1 <> key.`1) => FMap."_.[_]" (program_trials t msg ys) key = FMap."_.[_]" t key.
  elim=> [|y ys ih] t ha; first by rewrite /program_trials /=.
  have hat : forall z, z \in ys => z.`1.`1 <> key.`1 by smt(in_cons); have hy : y.`1.`1 <> key.`1 by smt(in_cons); have ht := ih (FMap."_.[_<-_]" t (y.`1.`1,msg) y.`2) hat; move: ht; rewrite /program_trials /= FMap.get_setE; smt().
  have hy : y.`1.`1 <> key.`1 by smt(in_cons).
  have ht := ih (FMap."_.[_<-_]" t (y.`1.`1,msg) y.`2) hat; move: ht; rewrite /program_trials /= FMap.get_setE; smt().
  rewrite (hfold ls full havoid) hbase.
  done.
qed.

op hidden_collision (ws : high list list)
  (logs : ((high list*vector)*Rq) list list) =
  has (fun w => hidden_hit w logs) ws.

lemma hidden_collision_count ws logs :
  hidden_collision ws logs = (0 < batch_hits ws logs).
proof.
  rewrite /hidden_collision /hidden_hit /batch_hits -has_count.
  rewrite eq_iff; split.
  - move/List.hasP=> [w [hw hh]].
    move/List.hasP: hh => [x [hx he]].
    apply/List.hasP; exists x; smt().
  move/List.hasP=> [x [hx hw]].
  apply/List.hasP; exists x.`1.`1; split; first exact hw.
  apply/List.hasP; exists x; smt().
qed.

lemma hidden_collision_indicator ws logs :
  b2r (hidden_collision ws logs) <= (batch_hits ws logs)%r.
proof.
  rewrite hidden_collision_count; have hg := batch_hits_ge0 ws logs.
  case (0 < batch_hits ws logs); rewrite /b2r /=; smt().
qed.

lemma batch_collision_bound sk0 ws n0 &m :
  SD.check sk0 => 0 <= n0 =>
  Pr[BatchLogs.run(sk0,n0) @ &m : hidden_collision ws res] <=
    n0%r*log_hit_cost sk0 ws.
proof.
(* COMPLETE THIS *)
  move=> hsk hn.
  byehoare (_ : xr_guard (arg=(sk0,n0))
    (xr_ofreal (n0%r*log_hit_cost sk0 ws)) ==>
    xr_ofreal (b2r (hidden_collision ws res))) => //.
  conseq (batch_logs_hit_cost sk0 ws n0 hsk hn).
  move=> &hr; apply Xreal.xle_cxr_l.
  move=> result; apply Xreal.Rpbar.xle_rle.
  split; first by rewrite /b2r; smt().
  move=> _; exact (hidden_collision_indicator ws result).
  by [].
  move=> &hr; apply Xreal.xle_cxr_r; move=> hdom; exact (hdom res{hr}).
qed.

module SequentialRawTranscript = {
  proc run(sk : SD.SK, msg : M, table : (high list*M,Rq) FMap.fmap) = {
    var w,st,c,oz;
    w <- witness; c <- witness; oz <- None;
    while (oz=None) {
      (w,st) <$ SD.commit sk;
      c <$ dC tau;
      if (FMap.dom table (w,msg)) { c <- oget (FMap."_.[_]" table (w,msg)); }
      table <- FMap."_.[_<-_]" table (w,msg) c;
      oz <- SD.respond sk c st;
    }
    return (table,(w,c,oget oz));
  }
}.

module JointRawTranscript = {
  proc run(sk : SD.SK, msg : M, table : (high list*M,Rq) FMap.fmap) = {
    var x,w,c,oz;
    w <- witness; c <- witness; oz <- None;
    while (oz=None) {
      x <$ SD.commit sk `*` dC tau;
      w <- x.`1.`1; c <- x.`2;
      if (FMap.dom table (w,msg)) { c <- oget (FMap."_.[_]" table (w,msg)); }
      table <- FMap."_.[_<-_]" table (w,msg) c;
      oz <- SD.respond sk c x.`1.`2;
    }
    return (table,(w,c,oget oz));
  }
}.

lemma sequential_joint_raw : equiv
  [SequentialRawTranscript.run ~ JointRawTranscript.run : ={arg} ==> ={res}].
proof.
(* COMPLETE THIS *)
  proc; while (={sk,msg,table,w,c,oz}).
  - seq 2 3 : (={sk,msg,table,w,c} /\ st{1}=x{2}.`1.`2).
  + wp; rndsem*{1} 0.
  rnd (fun (t : S.sT list * vector * Rq) => ((t.`1, t.`2), t.`3)) (fun (x : (S.sT list * vector) * Rq) => (x.`1.`1, x.`1.`2, x.`2)); skip; progress.
  by clear H; case xR => [[a b] c].
  rewrite -(dmap_dprodE _ _ (fun (x : (S.sT list * vector) * Rq) => (x.`1.`1, x.`1.`2, x.`2))).
  rewrite (dmap1E_can _ _ (fun (t : S.sT list * vector * Rq) => ((t.`1, t.`2), t.`3))).
  by move=> [a b c].
  by move=> [[a b] c].
  by clear H H0; case xR => [[a b] c].
  move: H1; rewrite -(dmap_dprodE _ _ (fun (x : (S.sT list * vector) * Rq) => (x.`1.`1, x.`1.`2, x.`2))) supp_dmap.
  by move=> [[[a b] c] [hin ->]].
  by clear H1 H2; case wstcL => [a b c].
  by auto => />.
  by auto => />.
qed.

local module MonitoredLogOracle (Policy : HiddenHashPolicy) = {
  import var Programmed
  proc h(w : high list, msg : M) = {
    var c;
    c <- witness;
    if (countH < external_budget) {
      RejectMonitor.seen <- w::RejectMonitor.seen;
      c <$ dC tau;
      if (hidden_hit w HiddenLogs.all) {
        RejectMonitor.bad <- true;
        c <@ Policy.choose(table,RejectMonitor.visible,(w,msg),c);
      } else {
        c <- if FMap.dom RejectMonitor.visible (w,msg)
          then oget (FMap."_.[_]" RejectMonitor.visible (w,msg)) else c;
      }
      table <- FMap."_.[_<-_]" table (w,msg) c;
      RejectMonitor.visible <- FMap."_.[_<-_]" RejectMonitor.visible (w,msg) c;
      countH <- countH+1;
    }
    return c;
  }
  proc sign(msg : M) = {
    var ls,x,sig;
    sig <- (witness,witness,oget None);
    if (countS < qS) {
      ls <@ HiddenLogs.take_eager();
      x <$ accepted_distribution sk;
      table <- program_trials table msg (rcons ls x);
      RejectMonitor.visible <- FMap."_.[_<-_]" RejectMonitor.visible (x.`1.`1,msg) x.`2;
      sig <- oget (trial_transcript sk x);
    }
    return sig;
  }
}.

local module PreloadedMonitoredGame (B : SD.FSaG.DSS.Adv_EFCMA_RO)
  (Policy : HiddenHashPolicy) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r;
    Programmed.init(sk);
    HiddenLogs.queue <- []; HiddenLogs.all <- [];
    RejectMonitor.visible <- FMap.empty;
    RejectMonitor.seen <- []; RejectMonitor.bad <- false;
    HiddenLogs.fill();
    r <@ ROMAdversary(B,MonitoredLogOracle(Policy)).distinguish(pk);
    return r;
  }
}.

local lemma hidden_hash_upto
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-HiddenLogs,-RejectMonitor}) pk sk &m :
  Pr[PreloadedMonitoredGame(B,FullHashPolicy).main(pk,sk) @ &m : res /\ !RejectMonitor.bad] =
  Pr[PreloadedMonitoredGame(B,VisibleHashPolicy).main(pk,sk) @ &m : res /\ !RejectMonitor.bad].
proof. byupto. qed.

local lemma hidden_hash_nonbad
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-HiddenLogs,-RejectMonitor}) pk sk &m :
  Pr[PreloadedMonitoredGame(B,FullHashPolicy).main(pk,sk) @ &m : !RejectMonitor.bad] =
  Pr[PreloadedMonitoredGame(B,VisibleHashPolicy).main(pk,sk) @ &m : !RejectMonitor.bad].
proof. byupto. qed.

local module RawCore = {
  import var Programmed
  proc h(w : high list, msg : M) = {
    var c;
    c <$ dC tau;
    if (!FMap.dom table (w,msg)) {
      table <- FMap."_.[_<-_]" table (w,msg) c;
    }
    return oget (FMap."_.[_]" table (w,msg));
  }
  proc sign(msg : M) = {
    var x,w,c,oz;
    w <- witness; c <- witness; oz <- None;
    while (oz=None) {
      x <$ SD.commit sk `*` dC tau;
      w <- x.`1.`1; c <- x.`2;
      if (FMap.dom table (w,msg)) {
        c <- oget (FMap."_.[_]" table (w,msg));
      }
      table <- FMap."_.[_<-_]" table (w,msg) c;
      oz <- SD.respond sk c x.`1.`2;
    }
    return (w,c,oget oz);
  }
}.

module NullOracle = {
  proc h(w : high list, msg : M) : Rq = { return witness; }
  proc sign(msg : M) : high list*Rq*SD.response_t = {
    return (witness,witness,oget None);
  }
}.

local module CapMonitor = { var bad : bool }.

local module MarkedExcess (Excess : SD.CMAtoKOA.R1.Oracle) = {
  proc h(w : high list, msg : M) = {
    var c;
    CapMonitor.bad <- true;
    c <@ Excess.h(w,msg);
    return c;
  }
  proc sign(msg : M) = {
    var sig;
    CapMonitor.bad <- true;
    sig <@ Excess.sign(msg);
    return sig;
  }
}.

local module CapBranches (O : SD.CMAtoKOA.R1.Oracle)
  (Excess : SD.CMAtoKOA.R1.Oracle) = {
  proc h = O.h
  proc sign = O.sign
  proc excess_h = MarkedExcess(Excess).h
  proc excess_sign = MarkedExcess(Excess).sign
}.

local module CapOracle (O : SD.CMAtoKOA.R1.Oracle)
  (Excess : SD.CMAtoKOA.R1.Oracle) = CountedGate(CapBranches(O,Excess)).

local module CappedExperiment (B : SD.FSaG.DSS.Adv_EFCMA_RO)
  (Excess : SD.CMAtoKOA.R1.Oracle) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r;
    Programmed.init(sk);
    SD.CMAtoKOA.CountH.qh <- 0;
    SD.CMAtoKOA.CountS.qs <- 0;
    CapMonitor.bad <- false;
    r <@ ROMAdversary(B,CapOracle(RawCore,Excess)).distinguish(pk);
    return r;
  }
}.

local module RawCoreGame (B : SD.FSaG.DSS.Adv_EFCMA_RO) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r;
    Programmed.init(sk);
    r <@ ROMAdversary(B,RawCore).distinguish(pk);
    return r;
  }
}.

local lemma cap_raw_stop_upto
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-CapMonitor,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) pk sk &m :
  Pr[CappedExperiment(B,RawCore).main(pk,sk) @ &m : res /\ !CapMonitor.bad] =
  Pr[CappedExperiment(B,NullOracle).main(pk,sk) @ &m : res /\ !CapMonitor.bad].
proof. byupto. qed.

local lemma cap_raw_hash_same : equiv
  [CapOracle(RawCore,RawCore).h ~ RawCore.h :
    ={arg,Programmed.sk,Programmed.table} ==>
    ={res,Programmed.sk,Programmed.table}].
proof.
  proc; inline *; sp; if{1}; auto.
qed.

local lemma cap_raw_sign_same : equiv
  [CapOracle(RawCore,RawCore).sign ~ RawCore.sign :
    ={arg,Programmed.sk,Programmed.table} ==>
    ={res,Programmed.sk,Programmed.table}].
proof.
  proc; inline *; sp; if{1}.
  - sp; wp; while (={oz,w,c,Programmed.sk,Programmed.table} /\ msg0{1}=msg{2}).
    + sim.
    auto; smt().
  sp; wp; while (oz0{1}=oz{2} /\ w0{1}=w{2} /\ c0{1}=c{2} /\
    ={Programmed.sk,Programmed.table} /\ msg2{1}=msg{2}).
  - sim.
  auto; smt().
qed.

local lemma cap_raw_adversary_same
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-CapMonitor,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  equiv [ROMAdversary(B,CapOracle(RawCore,RawCore)).distinguish ~
    ROMAdversary(B,RawCore).distinguish :
    ={arg,glob B,Programmed.sk,Programmed.table} ==> ={res}].
proof.
  proc; wp; call cap_raw_hash_same.
  wp; call (_ : ={Programmed.sk,Programmed.table,ROMSign.qs}).
  - proc; wp; call cap_raw_sign_same; auto.
  - proc; wp; call cap_raw_hash_same; auto.
  auto.
qed.

local lemma capped_raw_same
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-CapMonitor,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  equiv [CappedExperiment(B,RawCore).main ~ RawCoreGame(B).main :
    ={arg,glob B} ==> ={res}].
proof.
  proc; call (cap_raw_adversary_same B); inline Programmed.init; auto.
qed.

local lemma gate_forge_recording
  (O <: GatedOracle {-A,-ROMSign,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  equiv [SD.CG.RedFSaG(RedS(A),ROMHash(CountedGate(O)),ROMSign(CountedGate(O))).forge ~
    BareOracleBudget(A,CountedGate(O)).run :
    ={arg,glob A,glob O,SD.CMAtoKOA.CountH.qh,SD.CMAtoKOA.CountS.qs} ==>
    ={res,SD.CMAtoKOA.CountH.qh,SD.CMAtoKOA.CountS.qs}].
proof.
  proc; inline *; wp.
  call (_ : ={glob O,SD.CMAtoKOA.CountH.qh,SD.CMAtoKOA.CountS.qs}).
  - proc; inline *; sim.
  - proc; inline *; sim.
  auto.
qed.

local lemma gate_recorded_budget
  (O <: GatedOracle {-A,-ROMSign,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [SD.CG.RedFSaG(RedS(A),ROMHash(CountedGate(O)),ROMSign(CountedGate(O))).forge :
    SD.CMAtoKOA.CountH.qh=0 /\ SD.CMAtoKOA.CountS.qs=0 ==>
    SD.CMAtoKOA.CountH.qh<=qH+qS /\ SD.CMAtoKOA.CountS.qs<=qS].
proof.
  conseq (gate_forge_recording O) (gate_bare_budget O); smt().
qed.

local lemma cap_final_hash_budget
  (Excess <: SD.CMAtoKOA.R1.Oracle {-A,-ROMSign,-CapMonitor,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [CapOracle(RawCore,Excess).h :
    SD.CMAtoKOA.CountH.qh<=qH+qS /\ SD.CMAtoKOA.CountS.qs<=qS ==>
    SD.CMAtoKOA.CountH.qh<=external_budget /\ SD.CMAtoKOA.CountS.qs<=qS].
proof.
  proc; inline MarkedExcess(Excess).h; sp; if; wp; call (_ : true); auto;
    rewrite /external_budget; smt().
qed.

local lemma cap_game_query_bound
  (Excess <: SD.CMAtoKOA.R1.Oracle {-A,-ROMSign,-CapMonitor,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [CappedExperiment(SD.CG.RedFSaG(RedS(A)),Excess).main : true ==>
    SD.CMAtoKOA.CountH.qh<=external_budget /\ SD.CMAtoKOA.CountS.qs<=qS].
proof.
  proc; inline ROMAdversary(SD.CG.RedFSaG(RedS(A)),CapOracle(RawCore,Excess)).distinguish; wp.
  call (cap_final_hash_budget Excess); wp.
  call (gate_recorded_budget (CapBranches(RawCore,Excess))).
  inline Programmed.init; auto.
qed.

op cap_overflow q s = external_budget < q \/ qS < s.

local lemma cap_hash_overflow
  (Excess <: SD.CMAtoKOA.R1.Oracle {-CapMonitor,-SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [CapOracle(RawCore,Excess).h :
    CapMonitor.bad => cap_overflow SD.CMAtoKOA.CountH.qh SD.CMAtoKOA.CountS.qs ==>
    CapMonitor.bad => cap_overflow SD.CMAtoKOA.CountH.qh SD.CMAtoKOA.CountS.qs].
proof.
  proc; inline MarkedExcess(Excess).h; sp; if; wp; call (_ : true); auto;
    rewrite /cap_overflow; smt().
qed.

local lemma cap_sign_overflow
  (Excess <: SD.CMAtoKOA.R1.Oracle {-CapMonitor,-SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [CapOracle(RawCore,Excess).sign :
    CapMonitor.bad => cap_overflow SD.CMAtoKOA.CountH.qh SD.CMAtoKOA.CountS.qs ==>
    CapMonitor.bad => cap_overflow SD.CMAtoKOA.CountH.qh SD.CMAtoKOA.CountS.qs].
proof.
  proc; inline MarkedExcess(Excess).sign; sp; if; wp; call (_ : true); auto;
    rewrite /cap_overflow; smt().
qed.

local lemma cap_game_overflow
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-CapMonitor,-SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS})
  (Excess <: SD.CMAtoKOA.R1.Oracle {-CapMonitor,-SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [CappedExperiment(B,Excess).main : true ==>
    CapMonitor.bad => cap_overflow SD.CMAtoKOA.CountH.qh SD.CMAtoKOA.CountS.qs].
proof.
  proc; inline ROMAdversary(B,CapOracle(RawCore,Excess)).distinguish;
  wp; call (cap_hash_overflow Excess); wp.
  call (_ : CapMonitor.bad => cap_overflow SD.CMAtoKOA.CountH.qh SD.CMAtoKOA.CountS.qs).
  - proc; wp; call (cap_sign_overflow Excess); auto.
  - proc; wp; call (cap_hash_overflow Excess); auto.
  inline Programmed.init; auto.
qed.

local lemma cap_game_safe
  (Excess <: SD.CMAtoKOA.R1.Oracle {-A,-ROMSign,-CapMonitor,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [CappedExperiment(SD.CG.RedFSaG(RedS(A)),Excess).main : true ==> !CapMonitor.bad].
proof.
  conseq (cap_game_query_bound Excess)
    (cap_game_overflow (SD.CG.RedFSaG(RedS(A))) Excess);
    rewrite /cap_overflow; smt().
qed.

local lemma eager_logged_hash :
  eager [HiddenLogs.fill();,
    LoggedOracle(EagerLogConsumer).h ~ LoggedOracle(LazyLogConsumer).h,
    HiddenLogs.fill(); :
    (={w,msg}) /\ ={glob HiddenLogs,glob Programmed} ==>
    ={res,glob HiddenLogs,glob Programmed}].
proof.
  eager proc; inline HiddenLogs.fill.
  swap{1} 1 3; sim.
qed.

local lemma eager_logged_sign :
  eager [HiddenLogs.fill();,
    LoggedOracle(EagerLogConsumer).sign ~ LoggedOracle(LazyLogConsumer).sign,
    HiddenLogs.fill(); :
    ={arg,glob HiddenLogs,glob Programmed} ==>
    ={res,glob HiddenLogs,glob Programmed}].
proof.
  eager proc.
  swap{1} 2 -1; swap{2} 4 -1; wp; sp.
  eager if.
  - by move=> &1 &2 />.
  - move=> &2 b; inline HiddenLogs.fill; call (_ : true); auto.
  - swap{2} 5 -3; wp; rnd; eager call eager_hidden_take; auto.
  inline HiddenLogs.fill; call (_ : true); first by sim.
  auto.
qed.

op bounded_count (n cap : int) = if n < cap then n else cap.

lemma bounded_count_guard n cap :
  (bounded_count n cap < cap) = (n < cap).
proof. rewrite /bounded_count; smt(). qed.

lemma bounded_count_step n cap :
  bounded_count (n+1) cap =
    if n < cap then bounded_count n cap+1 else bounded_count n cap.
proof. rewrite /bounded_count; smt(). qed.

op cap_raw_state (lsk rsk : SD.SK)
  (lt rt : (high list*M,Rq) FMap.fmap) lq ls rq rs =
  lsk=rsk /\ lt=rt /\ rq=bounded_count lq external_budget /\
  rs=bounded_count ls qS.

local lemma cap_null_raw_hash : equiv
  [CapOracle(RawCore,NullOracle).h ~ Monitored(RawCollision).h :
    ={arg} /\ cap_raw_state Programmed.sk{1} Programmed.sk{2}
      Programmed.table{1} Programmed.table{2}
      SD.CMAtoKOA.CountH.qh{1} SD.CMAtoKOA.CountS.qs{1}
      Programmed.countH{2} Programmed.countS{2} ==>
    ={res} /\ cap_raw_state Programmed.sk{1} Programmed.sk{2}
      Programmed.table{1} Programmed.table{2}
      SD.CMAtoKOA.CountH.qh{1} SD.CMAtoKOA.CountS.qs{1}
      Programmed.countH{2} Programmed.countS{2}].
proof.
  proc; inline *; sp; if.
  - rewrite /cap_raw_state; smt(bounded_count_guard).
  - auto; rewrite /cap_raw_state; smt(bounded_count_step).
  auto; rewrite /cap_raw_state; smt(bounded_count_step).
qed.

local lemma cap_null_raw_sign : equiv
  [CapOracle(RawCore,NullOracle).sign ~ Monitored(RawCollision).sign :
    ={arg} /\ cap_raw_state Programmed.sk{1} Programmed.sk{2}
      Programmed.table{1} Programmed.table{2}
      SD.CMAtoKOA.CountH.qh{1} SD.CMAtoKOA.CountS.qs{1}
      Programmed.countH{2} Programmed.countS{2} ==>
    ={res} /\ cap_raw_state Programmed.sk{1} Programmed.sk{2}
      Programmed.table{1} Programmed.table{2}
      SD.CMAtoKOA.CountH.qh{1} SD.CMAtoKOA.CountS.qs{1}
      Programmed.countH{2} Programmed.countS{2}].
proof.
  proc; inline *; wp; sp; if.
  - rewrite /cap_raw_state; smt(bounded_count_guard).
  - sp; wp.
    while (={w,c,oz,Programmed.sk,Programmed.table} /\ msg0{1}=msg{2} /\
      Programmed.countH{2}=bounded_count SD.CMAtoKOA.CountH.qh{1} external_budget /\
      Programmed.countS{2}+1=bounded_count SD.CMAtoKOA.CountS.qs{1} qS).
    + wp; rnd; auto; smt().
    auto; rewrite /cap_raw_state; smt(bounded_count_step).
  auto; rewrite /cap_raw_state; smt(bounded_count_step).
qed.

local lemma capped_no_overflow pk sk &m :
  Pr[CappedExperiment(SD.CG.RedFSaG(RedS(A)),RawCore).main(pk,sk) @ &m : res] =
  Pr[CappedExperiment(SD.CG.RedFSaG(RedS(A)),NullOracle).main(pk,sk) @ &m : res].
proof.
  have hl : Pr[CappedExperiment(SD.CG.RedFSaG(RedS(A)),RawCore).main(pk,sk) @ &m : res] =
    Pr[CappedExperiment(SD.CG.RedFSaG(RedS(A)),RawCore).main(pk,sk) @ &m : res /\ !CapMonitor.bad].
  - byequiv (_ : ={arg,glob A} ==> ={res} /\ !CapMonitor.bad{2}) => //.
    conseq (_ : _ ==> ={res}) _ (cap_game_safe RawCore).
    sim.
  have hr : Pr[CappedExperiment(SD.CG.RedFSaG(RedS(A)),NullOracle).main(pk,sk) @ &m : res] =
    Pr[CappedExperiment(SD.CG.RedFSaG(RedS(A)),NullOracle).main(pk,sk) @ &m : res /\ !CapMonitor.bad].
  - byequiv (_ : ={arg,glob A} ==> ={res} /\ !CapMonitor.bad{2}) => //.
    conseq (_ : _ ==> ={res}) _ (cap_game_safe NullOracle).
    sim.
  rewrite hl hr; exact (cap_raw_stop_upto (SD.CG.RedFSaG(RedS(A))) pk sk &m).
qed.

local lemma cap_null_raw_adversary
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-CapMonitor,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  equiv [ROMAdversary(B,CapOracle(RawCore,NullOracle)).distinguish ~
    ROMAdversary(B,Monitored(RawCollision)).distinguish :
    ={arg,glob B} /\ cap_raw_state Programmed.sk{1} Programmed.sk{2}
      Programmed.table{1} Programmed.table{2}
      SD.CMAtoKOA.CountH.qh{1} SD.CMAtoKOA.CountS.qs{1}
      Programmed.countH{2} Programmed.countS{2} ==> ={res}].
proof.
  proc; wp; call cap_null_raw_hash; wp.
  call (_ : ={ROMSign.qs} /\ cap_raw_state Programmed.sk{1} Programmed.sk{2}
      Programmed.table{1} Programmed.table{2}
      SD.CMAtoKOA.CountH.qh{1} SD.CMAtoKOA.CountS.qs{1}
      Programmed.countH{2} Programmed.countS{2}).
  - proc; wp; call cap_null_raw_sign; auto.
  - proc; wp; call cap_null_raw_hash; auto.
  auto.
qed.

local lemma cap_null_monitored_same
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-CapMonitor,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  equiv [CappedExperiment(B,NullOracle).main ~ MonitoredGame(B,RawCollision).main :
    ={arg,glob B} ==> ={res}].
proof.
  proc; call (cap_null_raw_adversary B); inline Programmed.init; auto.
  rewrite /cap_raw_state /bounded_count /external_budget; smt(qS_ge0 qH_ge0).
qed.

local lemma raw_core_monitored pk sk &m :
  Pr[RawCoreGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res] =
  Pr[MonitoredGame(SD.CG.RedFSaG(RedS(A)),RawCollision).main(pk,sk) @ &m : res].
proof.
  have he : Pr[CappedExperiment(SD.CG.RedFSaG(RedS(A)),RawCore).main(pk,sk) @ &m : res] =
    Pr[RawCoreGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res].
  - byequiv (capped_raw_same (SD.CG.RedFSaG(RedS(A)))) => //.
  rewrite -he (capped_no_overflow pk sk &m).
  byequiv (cap_null_monitored_same (SD.CG.RedFSaG(RedS(A)))) => //.
qed.

lemma queue_fill_initial sk0 n0 : 0 <= n0 =>
  hoare [QueueFill.run : arg=(sk0,n0,[],[]) ==>
    res.`1=res.`2 /\ size res.`2=n0].
proof.
  move=> hn; proc; while (queue=all /\ n=n0 /\ size queue<=n0).
  - wp; call (_ : true); auto; smt(List.size_rcons).
  auto; smt().
qed.

lemma queue_consume_valid n0 all0 :
  hoare [QueueConsume.take_eager : n=n0 /\ all=all0 /\ 0<n /\
    size queue=n /\ List.all (fun ls => ls \in all) queue ==>
    res.`1=n0-1 /\ size res.`2=n0-1 /\ res.`3=all0 /\
    List.all (fun ls => ls \in all0) res.`2 /\ res.`4 \in all0].
proof.
(* COMPLETE THIS *)
  proc; auto.
  move=> &hr [hn [ha [hpos [hsize hall]]]].
  rewrite hpos /=.
  move: hsize hall.
  case: (queue{hr}) => //=.
  smt().
  smt().
qed.

lemma queue_fill_batch : equiv
  [QueueFill.run ~ FailedBatch.run :
    ={sk,n} /\ queue{1}=[] /\ all{1}=[] ==>
    res{1}.`1=res{2} /\ res{1}.`2=res{2}].
proof.
  proc; while (={sk,n} /\ queue{1}=all{1} /\ queue{1}=logs{2} /\
    size queue{1}=i{2}).
  - wp; call (_ : true); first by sim.
    auto; smt(List.size_rcons).
  auto.
qed.

lemma failed_batch_collision_bound sk0 ws n0 &m :
  SD.check sk0 => 0 <= n0 =>
  Pr[FailedBatch.run(sk0,n0) @ &m : hidden_collision ws res] <=
    n0%r*log_hit_cost sk0 ws.
proof.
  move=> hsk hn.
  have he : Pr[FailedBatch.run(sk0,n0) @ &m : hidden_collision ws res] =
    Pr[BatchLogs.run(sk0,n0) @ &m : hidden_collision ws res].
  - byequiv failed_batch_projection => //.
  rewrite he; exact (batch_collision_bound sk0 ws n0 &m hsk hn).
qed.

module type OracleDistinguisher (O : SD.CMAtoKOA.R1.Oracle) = {
  proc distinguish(pk : SD.PK) : bool
}.

local lemma eager_logged_distinguisher
  (D <: OracleDistinguisher {-HiddenLogs,-Programmed}) :
  eager [HiddenLogs.fill();,
    D(LoggedOracle(EagerLogConsumer)).distinguish ~
    D(LoggedOracle(LazyLogConsumer)).distinguish,
    HiddenLogs.fill(); :
    ={arg,glob D,glob HiddenLogs,glob Programmed} ==>
    ={res,glob D,glob HiddenLogs,glob Programmed}].
proof.
  eager proc (={glob HiddenLogs,glob Programmed}) => //; try by sim.
  - exact eager_logged_hash.
  exact eager_logged_sign.
qed.

local lemma eager_lazy_logged
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-HiddenLogs,-Programmed,-ROMSign}) :
  equiv [EagerLoggedGame(B).main ~ LazyLoggedGame(B).main :
    ={arg,glob B,ROMSign.qs} ==> ={res}].
proof.
  proc; seq 3 3 : (={glob HiddenLogs,glob Programmed,glob B,ROMSign.qs,pk}).
  - inline Programmed.init; auto.
  eager call (eager_logged_distinguisher (ROMAdversary(B))); auto.
qed.

local module RealCMAFixed (B : SD.FSaG.DSS.Adv_EFCMA_RO) = {
  proc run(ks : SD.PK*SD.SK) = {
    var msg,sig,v,f,n;
    SD.RO_G.init();
    SD.O_CMA_Default_G(SD.OpBasedSigG(SD.RO_G)).init(ks.`2);
    (msg,sig) <@ B(SD.RO_G,SD.O_CMA_Default_G(SD.OpBasedSigG(SD.RO_G))).forge(ks.`1);
    v <@ SD.OpBasedSigG(SD.RO_G).verify(ks.`1,msg,sig);
    f <@ SD.O_CMA_Default_G(SD.OpBasedSigG(SD.RO_G)).fresh(msg);
    n <@ SD.O_CMA_Default_G(SD.OpBasedSigG(SD.RO_G)).nr_queries();
    return n<=qS /\ v /\ f;
  }
}.

local module RawKeyed (B : SD.FSaG.DSS.Adv_EFCMA_RO) = {
  proc run(ks : SD.PK*SD.SK) = {
    var r;
    r <@ RawCoreGame(B).main(ks.`1,ks.`2);
    return r;
  }
}.

local lemma real_cma_average &m :
  Pr[SD.EF_CMA_RO_G(SD.OpBasedSigG,SD.CG.RedFSaG(RedS(A)),SD.RO_G,
    SD.O_CMA_Default_G).main() @ &m : res] =
  E SD.keygen (fun ks => Pr[RealCMAFixed(SD.CG.RedFSaG(RedS(A))).run(ks) @ &m : res]).
proof.
  rewrite -(key_average_probability (RealCMAFixed(SD.CG.RedFSaG(RedS(A)))) &m).
  byequiv (_ : ={glob A} ==> res{1}=res{2}.`2) => //.
  proc; inline *; wp; rnd; wp.
  call (_ : ={SD.RO_G.m,SD.O_CMA_Default_G.sk,SD.O_CMA_Default_G.qs}).
  - by sim.
  - by sim.
  auto.
qed.

local lemma real_sign_sequential : equiv
  [SD.OpBasedSigG(SD.RO_G).sign ~ SequentialRawTranscript.run :
    sk{1}=sk{2} /\ m{1}=msg{2} /\ SD.RO_G.m{1}=table{2} ==>
    res{1}=(res{2}.`2.`1,res{2}.`2.`3) /\ SD.RO_G.m{1}=res{2}.`1].
proof.
  proc; inline *.
  while (={sk,w,c,oz} /\ m{1}=msg{2} /\ SD.RO_G.m{1}=table{2}).
  - wp; rnd; wp; rnd; auto => &1 &2 />.
    move=> ws hws rr hr.
    case (FMap.dom table{2} (ws.`1,msg{2})) => hc.
    + rewrite /= (FMap.set_get table{2} (ws.`1,msg{2}) hc); smt().
    rewrite /= FMap.get_set_sameE /=; smt().
  auto.
qed.

local module RawSequential = {
  import var Programmed
  proc h = RawCore.h
  proc sign(msg : M) = {
    var sig;
    (table,sig) <@ SequentialRawTranscript.run(sk,msg,table);
    return sig;
  }
}.

local lemma raw_sequential_core : equiv
  [RawSequential.sign ~ RawCore.sign :
    ={arg,Programmed.sk,Programmed.table} ==>
    ={res,Programmed.sk,Programmed.table}].
proof.
  proc.
  transitivity* {1} {
    (Programmed.table,sig) <@ JointRawTranscript.run(Programmed.sk,msg,Programmed.table);
  }.
  - call sequential_joint_raw; auto.
  inline JointRawTranscript.run.
  sp; wp; while (={Programmed.sk,w,c,oz} /\ sk{1}=Programmed.sk{1} /\
    msg0{1}=msg{2} /\ table{1}=Programmed.table{2}).
  - wp; rnd; auto; smt().
  auto; smt().
qed.

local lemma real_cma_sign_sequential : equiv
  [SD.O_CMA_Default_G(SD.OpBasedSigG(SD.RO_G)).sign ~ ROMSign(RawSequential).sign :
    ={arg} /\ SD.O_CMA_Default_G.sk{1}=Programmed.sk{2} /\
    SD.RO_G.m{1}=Programmed.table{2} /\ SD.O_CMA_Default_G.qs{1}=ROMSign.qs{2} ==>
    ={res} /\ SD.O_CMA_Default_G.sk{1}=Programmed.sk{2} /\
    SD.RO_G.m{1}=Programmed.table{2} /\ SD.O_CMA_Default_G.qs{1}=ROMSign.qs{2}].
proof.
  proc; inline RawSequential.sign; sp; wp; call real_sign_sequential; auto.
qed.

local lemma rom_sign_sequential_core : equiv
  [ROMSign(RawSequential).sign ~ ROMSign(RawCore).sign :
    ={arg,Programmed.sk,Programmed.table,ROMSign.qs} ==>
    ={res,Programmed.sk,Programmed.table,ROMSign.qs}].
proof. proc; wp; call raw_sequential_core; auto. qed.

local lemma real_cma_sign_raw : equiv
  [SD.O_CMA_Default_G(SD.OpBasedSigG(SD.RO_G)).sign ~ ROMSign(RawCore).sign :
    ={arg} /\ SD.O_CMA_Default_G.sk{1}=Programmed.sk{2} /\
    SD.RO_G.m{1}=Programmed.table{2} /\ SD.O_CMA_Default_G.qs{1}=ROMSign.qs{2} ==>
    ={res} /\ SD.O_CMA_Default_G.sk{1}=Programmed.sk{2} /\
    SD.RO_G.m{1}=Programmed.table{2} /\ SD.O_CMA_Default_G.qs{1}=ROMSign.qs{2}].
proof.
  proc*; rewrite equiv[{2} 1 -rom_sign_sequential_core].
  call real_cma_sign_sequential; auto.
qed.

local lemma real_fixed_raw
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-SD.RO_G,-SD.O_CMA_Default_G,
    -SD.OpBased.P,-Programmed,-ROMSign}) :
  equiv [RealCMAFixed(B).run ~ RawKeyed(B).run :
    ={arg,glob B} ==> res{1} => res{2}].
proof.
  proc; inline *; wp; rnd; wp.
  call (_ : SD.O_CMA_Default_G.sk{1}=Programmed.sk{2} /\
    SD.RO_G.m{1}=Programmed.table{2} /\ SD.O_CMA_Default_G.qs{1}=ROMSign.qs{2}).
  - conseq real_cma_sign_raw; smt().
  - proc; inline *; auto => &1 &2 />; smt().
  auto => &1 &2 />; smt().
qed.

lemma program_transcript_log_all : equiv
  [ProgramTranscript.run ~ LogTranscript.run : ={arg} ==> ={res}].
proof.
  proc*; exlim table{1} => table0.
  call (program_transcript_log table0); auto.
qed.

module type TranscriptProgram = {
  proc run(sk : SD.SK, msg : M, table : (high list*M,Rq) FMap.fmap) :
    (high list*M,Rq) FMap.fmap * (high list*Rq*SD.response_t)
}.

module SeparateTranscript = {
  proc run(sk : SD.SK, msg : M, table : (high list*M,Rq) FMap.fmap) = {
    var ls,x;
    (ls,x) <@ SeparateTrials.run(sk);
    return (program_trials table msg (rcons ls x),oget (trial_transcript sk x));
  }
}.

lemma log_separate_transcript : equiv
  [LogTranscript.run ~ SeparateTranscript.run :
    ={arg} /\ SD.check arg{1}.`1 ==> ={res}].
proof.
  proc; wp; call logged_trials_separate; auto.
qed.

local module SampledProgram (T : TranscriptProgram) = {
  include var Programmed [init,h]
  proc sign(msg : M) = {
    var sig;
    sig <- (witness,witness,oget None);
    if (countS < qS) {
      (table,sig) <@ T.run(sk,msg,table);
      countS <- countS+1;
    }
    return sig;
  }
}.

local module SampledProgramGame (B : SD.FSaG.DSS.Adv_EFCMA_RO)
  (T : TranscriptProgram) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r;
    Programmed.init(sk);
    r <@ ROMAdversary(B,SampledProgram(T)).distinguish(pk);
    return r;
  }
}.

local lemma sampled_program_congr
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign})
  (T1 <: TranscriptProgram {-B,-Programmed,-ROMSign})
  (T2 <: TranscriptProgram {-B,-Programmed,-ROMSign}) :
  equiv [T1.run ~ T2.run : ={arg} /\ SD.check arg{1}.`1 ==> ={res}] =>
  equiv [SampledProgramGame(B,T1).main ~ SampledProgramGame(B,T2).main :
    ={arg,glob B} /\ SD.check arg{1}.`2 ==> ={res}].
proof.
  move=> he; proc.
  call (_ : ={arg,glob B,glob Programmed} /\ SD.check Programmed.sk{1} ==> ={res}).
  - proc; wp; call (_ : ={arg,glob Programmed} ==> ={res,glob Programmed}).
    + proc; inline *; sp; if; auto.
    wp; call (_ : ={glob Programmed,ROMSign.qs} /\ SD.check Programmed.sk{1}).
    + proc; inline ROMSign(SampledProgram(T1)).sign ROMSign(SampledProgram(T2)).sign.
      inline SampledProgram(T1).sign SampledProgram(T2).sign.
      sp; if; first by move=> &1 &2 />.
      * wp; call he; auto.
      auto.
    + proc; inline *; sp; if; auto.
    auto.
  inline Programmed.init; auto.
qed.

local lemma independent_response_sign : equiv
  [Monitored(IndependentCollision).sign ~ SampledProgram(ResponseProgram).sign :
    ={arg,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH} ==>
    ={res,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH}].
proof.
  proc; inline *; wp; sp; if; first by move=> &1 &2 />.
  - sp; wp.
    while (={Programmed.sk,Programmed.countS,Programmed.countH,oz} /\
      sk{2}=Programmed.sk{2} /\ msg{1}=msg0{2} /\
      Programmed.table{1}=table{2} /\
      (oz{1}<>None => w{1}=x{2}.`1.`1 /\ c{1}=x{2}.`2)).
    + wp; rnd; auto; smt().
    auto; smt().
  auto.
qed.

local lemma independent_response_game
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign}) :
  equiv [MonitoredGame(B,IndependentCollision).main ~
    SampledProgramGame(B,ResponseProgram).main : ={arg,glob B} ==> ={res}].
proof.
  proc; call (_ : ={arg,glob B,Programmed.sk,Programmed.table,
    Programmed.countS,Programmed.countH} ==> ={res}).
  - proc; wp; call (_ : ={arg,Programmed.sk,Programmed.table,
      Programmed.countS,Programmed.countH} ==>
      ={res,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH}).
    + proc; inline *; sp; if; auto.
    wp; call (_ : ={Programmed.sk,Programmed.table,Programmed.countS,
      Programmed.countH,ROMSign.qs}).
    + proc; wp; call independent_response_sign; auto.
    + proc; inline *; sp; if; auto.
    auto.
  inline Programmed.init; auto.
qed.

local lemma response_separate_game
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign}) :
  equiv [SampledProgramGame(B,ResponseProgram).main ~
    SampledProgramGame(B,SeparateTranscript).main :
    ={arg,glob B} /\ SD.check arg{1}.`2 ==> ={res}].
proof.
  have h1 := sampled_program_congr B ResponseProgram ProgramTranscript _.
  - conseq response_program_transcript; smt().
  have h2 := sampled_program_congr B ProgramTranscript LogTranscript _.
  - conseq program_transcript_log_all; smt().
  have h3 := sampled_program_congr B LogTranscript SeparateTranscript log_separate_transcript.
  proc*; rewrite equiv[{1} 1 h1].
  rewrite equiv[{1} 1 h2].
  call h3; auto.
qed.

local lemma separate_lazy_sign : equiv
  [SampledProgram(SeparateTranscript).sign ~ LoggedOracle(LazyLogConsumer).sign :
    ={arg,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH} /\
    HiddenLogs.queue{2}=[] ==>
    ={res,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH} /\
    HiddenLogs.queue{2}=[]].
proof.
  proc; inline SeparateTranscript.run SeparateTrials.run
    HiddenLogs.take_lazy QueueConsume.take_lazy.
  wp; sp; if; first by move=> &1 &2 />.
  - sp; rcondt{2} 1; first by auto; smt().
    rcondt{2} 1; first by auto.
    wp; rnd; wp; call (_ : true); first by sim.
    auto => &1 &2 />; smt().
  auto.
qed.

local lemma hidden_fill_ll sk0 : SD.check sk0 =>
  phoare [HiddenLogs.fill : Programmed.sk=sk0 ==> Programmed.sk=sk0] = 1%r.
proof.
  move=> hsk; proc; call (queue_fill_lossless sk0 hsk); auto.
qed.

local lemma separate_lazy_game
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-HiddenLogs}) sk0 :
  SD.check sk0 =>
  equiv [SampledProgramGame(B,SeparateTranscript).main ~ LazyLoggedGame(B).main :
    ={arg,glob B} /\ arg{1}.`2=sk0 ==> ={res}].
proof.
  move=> hsk; proc; call{2} (hidden_fill_ll sk0 hsk).
  call (_ : ={arg,glob B,Programmed.sk,Programmed.table,
      Programmed.countS,Programmed.countH} /\ HiddenLogs.queue{2}=[] /\
      Programmed.sk{2}=sk0 ==> ={res} /\ Programmed.sk{2}=sk0).
  - proc; wp; call (_ : ={arg,Programmed.sk,Programmed.table,
      Programmed.countS,Programmed.countH} ==>
      ={res,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH}).
    + proc; inline *; sp; if; auto.
    wp; call (_ : ={Programmed.sk,Programmed.table,Programmed.countS,
      Programmed.countH,ROMSign.qs} /\ HiddenLogs.queue{2}=[] /\ Programmed.sk{2}=sk0).
    + proc; wp; call separate_lazy_sign; auto.
    + proc; inline *; sp; if; auto.
    auto.
  inline Programmed.init; auto.
qed.

lemma hidden_tables_empty logs :
  hidden_tables_match FMap.empty FMap.empty logs.
proof. by rewrite /hidden_tables_match. qed.

lemma hidden_tables_set full visible logs key c :
  hidden_tables_match full visible logs =>
  hidden_tables_match (FMap."_.[_<-_]" full key c)
    (FMap."_.[_<-_]" visible key c) logs.
proof.
  move=> hm; rewrite /hidden_tables_match => k hk.
  rewrite !FMap.get_setE; have hh := hm k hk; smt().
qed.

op cached_value (table : (high list*M,Rq) FMap.fmap) key c =
  if FMap.dom table key then oget (FMap."_.[_]" table key) else c.

lemma hidden_cache_same full visible logs (key : high list*M) c :
  hidden_tables_match full visible logs => !hidden_hit key.`1 logs =>
  cached_value full key c = cached_value visible key c.
proof.
  move=> hm hh; have he := hm key hh.
  by rewrite /cached_value !FMap.domE he.
qed.

lemma hidden_full_hash_step full visible logs (key : high list*M) c :
  hidden_tables_match full visible logs =>
  let c' = if hidden_hit key.`1 logs then cached_value full key c
    else cached_value visible key c in
  let full' = FMap."_.[_<-_]" full key c' in
  full' = (if FMap.dom full key then full else FMap."_.[_<-_]" full key c) /\
  c' = oget (FMap."_.[_]" full' key) /\
  hidden_tables_match full' (FMap."_.[_<-_]" visible key c') logs.
proof.
  move=> hm.
  have hc : (if hidden_hit key.`1 logs then cached_value full key c
    else cached_value visible key c) = cached_value full key c.
  - case (hidden_hit key.`1 logs) => hh //=.
    rewrite eq_sym; exact (hidden_cache_same full visible logs key c hm hh).
  rewrite hc /=; split.
  - rewrite /cached_value; case (FMap.dom full key) => hd //=.
    exact (FMap.set_get full key hd).
  split; first by rewrite FMap.get_set_sameE.
  exact (hidden_tables_set full visible logs key (cached_value full key c) hm).
qed.

op log_queue_inv (queue logs : ((high list*vector)*Rq) list list) ns =
  0<=ns<=qS /\ size queue=qS-ns /\ List.all (fun ls => ls \in logs) queue.

local lemma hidden_take_valid :
  hoare [HiddenLogs.take_eager :
    log_queue_inv HiddenLogs.queue HiddenLogs.all Programmed.countS /\
    Programmed.countS<qS ==>
    log_queue_inv HiddenLogs.queue HiddenLogs.all Programmed.countS /\
    res \in HiddenLogs.all].
proof.
  proc; exlim Programmed.countS, HiddenLogs.all => ns logs.
  wp; call (queue_consume_valid (qS-ns) logs); auto.
  rewrite /log_queue_inv; smt().
qed.

local lemma hidden_take_coupled : equiv
  [HiddenLogs.take_eager ~ HiddenLogs.take_eager :
    ={glob HiddenLogs,Programmed.sk,Programmed.countS} /\
    log_queue_inv HiddenLogs.queue{2} HiddenLogs.all{2} Programmed.countS{2} /\
    Programmed.countS{2}<qS ==>
    ={res,glob HiddenLogs,Programmed.sk,Programmed.countS} /\
    log_queue_inv HiddenLogs.queue{2} HiddenLogs.all{2} Programmed.countS{2} /\
    res{2} \in HiddenLogs.all{2}].
proof.
  conseq (_ : _ ==> ={res,glob HiddenLogs,Programmed.sk,Programmed.countS})
    _ hidden_take_valid.
  - by move=> &1 &2 />.
  sim.
qed.

local lemma hidden_take_hmatch :
  hoare [HiddenLogs.take_eager :
    hidden_tables_match Programmed.table RejectMonitor.visible HiddenLogs.all ==>
    hidden_tables_match Programmed.table RejectMonitor.visible HiddenLogs.all].
proof. proc; inline QueueConsume.take_eager; auto. qed.

local lemma hidden_take_matched : equiv
  [HiddenLogs.take_eager ~ HiddenLogs.take_eager :
    ={glob HiddenLogs,Programmed.sk,Programmed.countS} /\
    log_queue_inv HiddenLogs.queue{2} HiddenLogs.all{2} Programmed.countS{2} /\
    Programmed.countS{2}<qS /\
    hidden_tables_match Programmed.table{2} RejectMonitor.visible{2} HiddenLogs.all{2} ==>
    ={res,glob HiddenLogs,Programmed.sk,Programmed.countS} /\
    log_queue_inv HiddenLogs.queue{2} HiddenLogs.all{2} Programmed.countS{2} /\
    res{2} \in HiddenLogs.all{2} /\
    hidden_tables_match Programmed.table{2} RejectMonitor.visible{2} HiddenLogs.all{2}].
proof.
  conseq hidden_take_coupled _ hidden_take_hmatch; smt().
qed.

op hidden_budget sk =
  qS%r*external_budget%r*p_max (dfst (SD.commit sk))/(1%r-p_rej).

lemma failed_batch_budget sk0 ws &m : SD.check sk0 => size ws<=external_budget =>
  Pr[FailedBatch.run(sk0,qS) @ &m : hidden_collision ws res] <= hidden_budget sk0.
proof.
(* COMPLETE THIS *)
  move=> hsk hsize.
  have hb := failed_batch_collision_bound sk0 ws qS &m hsk qS_ge0.
  apply (ler_trans (qS%r*log_hit_cost sk0 ws)); first exact hb.
  rewrite /hidden_budget /log_hit_cost.
  have hp := rejection_range.
  have he := ge0_pmax (dfst (SD.commit sk0)).
  have hs : 0%r<=qS%r by rewrite le_fromint; exact qS_ge0.
  have hw : (size ws)%r<=external_budget%r by rewrite le_fromint.
  clear hb hsk hsize.
  move: hp he hs hw.
  move: (p_max (dfst (SD.commit sk0))) (qS%r) ((size ws)%r) (external_budget%r) p_rej => e s w b p hp he hs hw.
  have hi : 0%r <= inv (1%r - p) by rewrite invr_ge0; smt().
  smt().
qed.

module CheckBatch = {
  proc run(sk : SD.SK, ws : high list list) = {
    var logs;
    logs <@ FailedBatch.run(sk,qS);
    return hidden_collision ws logs;
  }
}.

lemma check_batch_probability sk0 ws0 &m :
  Pr[CheckBatch.run(sk0,ws0) @ &m : res] =
  Pr[FailedBatch.run(sk0,qS) @ &m : hidden_collision ws0 res].
proof.
  byequiv (_ : arg{1}=(sk0,ws0) /\ arg{2}=(sk0,qS) ==>
    res{1}=hidden_collision ws0 res{2}) => //.
  proc*; inline CheckBatch.run; wp; call (_ : true); first by sim.
  auto.
qed.

lemma check_batch_bound sk0 : SD.check sk0 =>
  phoare [CheckBatch.run : sk=sk0 /\ size ws<=external_budget ==> res] <= (hidden_budget sk0).
proof.
  move=> hsk; bypr=> &m [hkey hsize].
  rewrite hkey (check_batch_probability sk0 ws{m} &m).
  exact (failed_batch_budget sk0 ws{m} &m hsk hsize).
qed.

module AcceptedDraw = {
  proc run(sk : SD.SK) = {
    var x;
    x <$ accepted_distribution sk;
    return oget (trial_transcript sk x);
  }
}.

lemma accepted_draw_correct sk0 : SD.check sk0 =>
  equiv [AcceptedTranscript.run ~ AcceptedDraw.run :
    ={arg} /\ arg{1}=sk0 ==> ={res}].
proof.
  move=> hsk; proc.
  transitivity* {1} {
    (ls,x) <@ SeparateTrials.run(sk);
  }.
  - call logged_trials_separate; auto.
  inline SeparateTrials.run; wp; rnd.
  call{1} (failed_log_lossless sk0 hsk); auto.
qed.

local lemma preloaded_full_hash : equiv
  [LoggedOracle(EagerLogConsumer).h ~ MonitoredLogOracle(FullHashPolicy).h :
    ={arg,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH} /\
    hidden_tables_match Programmed.table{2} RejectMonitor.visible{2} HiddenLogs.all{2} ==>
    ={res,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH} /\
    hidden_tables_match Programmed.table{2} RejectMonitor.visible{2} HiddenLogs.all{2}].
proof.
  proc; inline *; sp; if; first by move=> &1 &2 />.
  - auto => &1 &2 />.
    move=> hm hcap c hc.
    have hh := hidden_full_hash_step Programmed.table{2} RejectMonitor.visible{2}
      HiddenLogs.all{2} (w{2},msg{2}) c hm.
    rewrite /cached_value in hh; smt().
  auto.
qed.

local lemma preloaded_full_sign : equiv
  [LoggedOracle(EagerLogConsumer).sign ~ MonitoredLogOracle(FullHashPolicy).sign :
    ={arg,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH,glob HiddenLogs} /\
    log_queue_inv HiddenLogs.queue{2} HiddenLogs.all{2} Programmed.countS{2} /\
    hidden_tables_match Programmed.table{2} RejectMonitor.visible{2} HiddenLogs.all{2} ==>
    ={res,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH,glob HiddenLogs} /\
    log_queue_inv HiddenLogs.queue{2} HiddenLogs.all{2} Programmed.countS{2} /\
    hidden_tables_match Programmed.table{2} RejectMonitor.visible{2} HiddenLogs.all{2}].
proof.
  proc; sp; if; first by move=> &1 &2 />.
  - wp; rnd; wp; call hidden_take_matched; auto => &1 &2 />.
    move=> _ _ _ _ _ _ ls logs queue ns _ _ _ _ hls hm x hx.
    exact (hidden_program_preserves Programmed.table{2} RejectMonitor.visible{2}
      logs msg{2} ls x hm hls).
  auto.
qed.

lemma queue_fill_initial_general n0 :
  hoare [QueueFill.run : queue=[] /\ all=[] /\ n=n0 /\ 0<=n ==>
    res.`1=res.`2 /\ size res.`2=n0].
proof.
  proc; while (queue=all /\ size queue<=n /\ n=n0).
  - wp; call (_ : true); auto; smt(List.size_rcons).
  auto; smt().
qed.

lemma queue_fill_initial_coupled n0 : equiv
  [QueueFill.run ~ QueueFill.run :
    ={arg} /\ queue{2}=[] /\ all{2}=[] /\ n{2}=n0 /\ 0<=n0 ==>
    ={res} /\ res{2}.`1=res{2}.`2 /\ size res{2}.`2=n0].
proof.
  conseq (_ : _ ==> ={res}) _ (queue_fill_initial_general n0).
  - by move=> &1 &2 />.
  sim.
qed.

local lemma preloaded_full_adversary
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-HiddenLogs,-RejectMonitor}) :
  equiv [ROMAdversary(B,LoggedOracle(EagerLogConsumer)).distinguish ~
    ROMAdversary(B,MonitoredLogOracle(FullHashPolicy)).distinguish :
    ={arg,glob B,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH,glob HiddenLogs} /\
    log_queue_inv HiddenLogs.queue{2} HiddenLogs.all{2} Programmed.countS{2} /\
    hidden_tables_match Programmed.table{2} RejectMonitor.visible{2} HiddenLogs.all{2} ==>
    ={res}].
proof.
  proc; wp; call preloaded_full_hash; wp.
  call (_ : ={Programmed.sk,Programmed.table,Programmed.countS,
    Programmed.countH,glob HiddenLogs,ROMSign.qs} /\
    log_queue_inv HiddenLogs.queue{2} HiddenLogs.all{2} Programmed.countS{2} /\
    hidden_tables_match Programmed.table{2} RejectMonitor.visible{2} HiddenLogs.all{2}).
  - proc; wp; call preloaded_full_sign; auto.
  - proc; wp; call preloaded_full_hash; auto.
  auto.
qed.

local lemma eager_preloaded_full
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-HiddenLogs,-RejectMonitor}) :
  equiv [EagerLoggedGame(B).main ~ PreloadedMonitoredGame(B,FullHashPolicy).main :
    ={arg,glob B} ==> ={res}].
proof.
  proc; call (preloaded_full_adversary B).
  inline HiddenLogs.fill; call (queue_fill_initial_coupled qS).
  inline Programmed.init; auto => &1 &2 />.
  rewrite /log_queue_inv; smt(qS_ge0 List.allP hidden_tables_empty).
qed.

local lemma raw_keyed_probability
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign}) pk sk &m :
  Pr[RawKeyed(B).run(pk,sk) @ &m : res] =
  Pr[RawCoreGame(B).main(pk,sk) @ &m : res].
proof.
  byequiv (_ : arg{1}=(pk,sk) /\ arg{2}=(pk,sk) /\ ={glob B} ==> ={res}) => //.
  proc*; inline RawKeyed(B).run; wp.
  call (_ : ={glob B}); first by sim.
  auto.
qed.

local lemma real_to_monitored pk sk &m :
  Pr[RealCMAFixed(SD.CG.RedFSaG(RedS(A))).run(pk,sk) @ &m : res] <=
  Pr[MonitoredGame(SD.CG.RedFSaG(RedS(A)),RawCollision).main(pk,sk) @ &m : res].
proof.
  have hb : Pr[RealCMAFixed(SD.CG.RedFSaG(RedS(A))).run(pk,sk) @ &m : res] <=
    Pr[RawKeyed(SD.CG.RedFSaG(RedS(A))).run(pk,sk) @ &m : res].
  - byequiv (real_fixed_raw (SD.CG.RedFSaG(RedS(A)))) => //.
  rewrite (raw_keyed_probability (SD.CG.RedFSaG(RedS(A))) pk sk &m)
    (raw_core_monitored pk sk &m) in hb.
  exact hb.
qed.

local lemma independent_to_eager pk sk &m : SD.check sk =>
  Pr[MonitoredGame(SD.CG.RedFSaG(RedS(A)),IndependentCollision).main(pk,sk) @ &m : res] =
  Pr[EagerLoggedGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res].
proof.
  move=> hsk.
  have h1 : Pr[MonitoredGame(SD.CG.RedFSaG(RedS(A)),IndependentCollision).main(pk,sk) @ &m : res] =
    Pr[SampledProgramGame(SD.CG.RedFSaG(RedS(A)),ResponseProgram).main(pk,sk) @ &m : res].
  - byequiv (independent_response_game (SD.CG.RedFSaG(RedS(A)))) => //.
  have h2 : Pr[SampledProgramGame(SD.CG.RedFSaG(RedS(A)),ResponseProgram).main(pk,sk) @ &m : res] =
    Pr[SampledProgramGame(SD.CG.RedFSaG(RedS(A)),SeparateTranscript).main(pk,sk) @ &m : res].
  - byequiv (response_separate_game (SD.CG.RedFSaG(RedS(A)))) => //.
  have h3 : Pr[SampledProgramGame(SD.CG.RedFSaG(RedS(A)),SeparateTranscript).main(pk,sk) @ &m : res] =
    Pr[LazyLoggedGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res].
  - byequiv (separate_lazy_game (SD.CG.RedFSaG(RedS(A))) sk hsk) => //.
  have h4 : Pr[EagerLoggedGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res] =
    Pr[LazyLoggedGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res].
  - byequiv (eager_lazy_logged (SD.CG.RedFSaG(RedS(A)))) => //.
  by rewrite h1 h2 h3 h4.
qed.

local lemma real_to_eager pk sk &m : SD.check sk =>
  Pr[RealCMAFixed(SD.CG.RedFSaG(RedS(A))).run(pk,sk) @ &m : res] <=
  Pr[EagerLoggedGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res] +
    trial_cost (p_max (dfst (SD.commit sk))) qS 0.
proof.
  move=> hsk; have h0 := real_to_monitored pk sk &m.
  have h1 := raw_independent_hop (SD.CG.RedFSaG(RedS(A))) pk sk &m hsk
    (stopped_fixed_game_ll pk sk &m hsk).
  rewrite (independent_to_eager pk sk &m hsk) in h1; smt().
qed.

local module VisibleAccepted = {
  import var Programmed
  proc h(w : high list, msg : M) = {
    var c;
    c <- witness;
    if (countH < external_budget) {
      RejectMonitor.seen <- w::RejectMonitor.seen;
      c <$ dC tau;
      c <- cached_value table (w,msg) c;
      table <- FMap."_.[_<-_]" table (w,msg) c;
      countH <- countH+1;
    }
    return c;
  }
  proc sign(msg : M) = {
    var x,sig;
    sig <- (witness,witness,oget None);
    if (countS < qS) {
      x <$ accepted_distribution sk;
      table <- FMap."_.[_<-_]" table (x.`1.`1,msg) x.`2;
      countS <- countS+1;
      sig <- oget (trial_transcript sk x);
    }
    return sig;
  }
}.

local module VisibleBatchGame (B : SD.FSaG.DSS.Adv_EFCMA_RO) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r,logs;
    Programmed.init(sk);
    RejectMonitor.seen <- [];
    logs <@ FailedBatch.run(sk,qS);
    r <@ ROMAdversary(B,VisibleAccepted).distinguish(pk);
    return (r,hidden_collision RejectMonitor.seen logs);
  }
}.

local module DeferredBatchGame (B : SD.FSaG.DSS.Adv_EFCMA_RO) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r,bad;
    Programmed.init(sk);
    RejectMonitor.seen <- [];
    r <@ ROMAdversary(B,VisibleAccepted).distinguish(pk);
    bad <@ CheckBatch.run(sk,RejectMonitor.seen);
    return (r,bad);
  }
}.

local lemma visible_batch_deferred
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-RejectMonitor}) :
  equiv [VisibleBatchGame(B).main ~ DeferredBatchGame(B).main :
    ={arg,glob B} ==> ={res}].
proof.
  proc; inline CheckBatch.run; swap{1} 3 1; wp.
  call (_ : true); first by sim.
  wp; call (_ : ={glob B,glob Programmed,RejectMonitor.seen}); first by sim.
  inline Programmed.init; auto.
qed.

lemma hidden_collision_cons w ws logs :
  hidden_collision (w::ws) logs = (hidden_hit w logs \/ hidden_collision ws logs).
proof. by rewrite /hidden_collision /=. qed.

op visible_trace_relation (vis table : (high list*M,Rq) FMap.fmap)
  (all logs : ((high list*vector)*Rq) list list) seen bad =
  vis=table /\ all=logs /\ bad=hidden_collision seen logs.

local lemma preloaded_visible_hash (logs0 : ((high list*vector)*Rq) list list) : equiv
  [MonitoredLogOracle(VisibleHashPolicy).h ~ VisibleAccepted.h :
    ={arg,Programmed.sk,Programmed.countS,Programmed.countH,RejectMonitor.seen} /\
    visible_trace_relation RejectMonitor.visible{1} Programmed.table{2}
      HiddenLogs.all{1} logs0 RejectMonitor.seen{1} RejectMonitor.bad{1} ==>
    ={res,Programmed.sk,Programmed.countS,Programmed.countH,RejectMonitor.seen} /\
    visible_trace_relation RejectMonitor.visible{1} Programmed.table{2}
      HiddenLogs.all{1} logs0 RejectMonitor.seen{1} RejectMonitor.bad{1}].
proof.
  proc; inline *; sp; if; first by move=> &1 &2 />.
  - auto; rewrite /visible_trace_relation /cached_value.
    move=> &1 &2 /> hcap c hc.
    rewrite hidden_collision_cons.
    case (hidden_hit w{2} logs0); smt().
  auto.
qed.

local lemma preloaded_visible_sign (logs0 : ((high list*vector)*Rq) list list) : equiv
  [MonitoredLogOracle(VisibleHashPolicy).sign ~ VisibleAccepted.sign :
    ={arg,Programmed.sk,Programmed.countS,Programmed.countH,RejectMonitor.seen} /\
    visible_trace_relation RejectMonitor.visible{1} Programmed.table{2}
      HiddenLogs.all{1} logs0 RejectMonitor.seen{1} RejectMonitor.bad{1} ==>
    ={res,Programmed.sk,Programmed.countS,Programmed.countH,RejectMonitor.seen} /\
    visible_trace_relation RejectMonitor.visible{1} Programmed.table{2}
      HiddenLogs.all{1} logs0 RejectMonitor.seen{1} RejectMonitor.bad{1}].
proof.
  proc; inline HiddenLogs.take_eager QueueConsume.take_eager.
  sp; if; first by move=> &1 &2 />.
  - auto; rewrite /visible_trace_relation; move=> &1 &2 />; smt().
  auto.
qed.

local lemma preloaded_visible_batch
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-HiddenLogs,-RejectMonitor}) :
  equiv [PreloadedMonitoredGame(B,VisibleHashPolicy).main ~ VisibleBatchGame(B).main :
    ={arg,glob B} ==> res{1}=res{2}.`1 /\ RejectMonitor.bad{1}=res{2}.`2].
proof.
  proc; seq 7 3 : (={glob B,Programmed.sk,Programmed.countS,Programmed.countH,
    RejectMonitor.seen,pk} /\
    visible_trace_relation RejectMonitor.visible{1} Programmed.table{2}
      HiddenLogs.all{1} logs{2} RejectMonitor.seen{1} RejectMonitor.bad{1}).
  - inline HiddenLogs.fill; call queue_fill_batch.
    inline Programmed.init; auto => &1 &2 />.
  exlim logs{2} => logs0; wp.
  call (_ : ={arg,glob B,Programmed.sk,Programmed.countS,Programmed.countH,RejectMonitor.seen} /\
    visible_trace_relation RejectMonitor.visible{1} Programmed.table{2}
      HiddenLogs.all{1} logs0 RejectMonitor.seen{1} RejectMonitor.bad{1} ==>
    ={res,RejectMonitor.seen} /\
    visible_trace_relation RejectMonitor.visible{1} Programmed.table{2}
      HiddenLogs.all{1} logs0 RejectMonitor.seen{1} RejectMonitor.bad{1}).
  - proc; wp; call (preloaded_visible_hash logs0); wp.
    call (_ : ={Programmed.sk,Programmed.countS,Programmed.countH,RejectMonitor.seen,ROMSign.qs} /\
      visible_trace_relation RejectMonitor.visible{1} Programmed.table{2}
        HiddenLogs.all{1} logs0 RejectMonitor.seen{1} RejectMonitor.bad{1}).
    + proc; wp; call (preloaded_visible_sign logs0); auto.
    + proc; wp; call (preloaded_visible_hash logs0); auto.
    auto.
  auto; rewrite /visible_trace_relation; smt().
qed.

op visible_budget_inv (nh : int) (seen : high list list) =
  0<=nh<=external_budget /\ size seen=nh.

local lemma visible_hash_budget :
  hoare [VisibleAccepted.h : visible_budget_inv Programmed.countH RejectMonitor.seen ==>
    visible_budget_inv Programmed.countH RejectMonitor.seen].
proof.
  proc; sp; if.
  - wp; rnd; auto; rewrite /visible_budget_inv /=; smt().
  auto.
qed.

local lemma visible_sign_budget :
  hoare [VisibleAccepted.sign : visible_budget_inv Programmed.countH RejectMonitor.seen ==>
    visible_budget_inv Programmed.countH RejectMonitor.seen].
proof. proc; sp; if; auto. qed.

local lemma visible_adversary_budget
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-RejectMonitor}) :
  hoare [ROMAdversary(B,VisibleAccepted).distinguish :
    visible_budget_inv Programmed.countH RejectMonitor.seen ==>
    visible_budget_inv Programmed.countH RejectMonitor.seen].
proof.
  proc; wp; call visible_hash_budget; wp.
  call (_ : visible_budget_inv Programmed.countH RejectMonitor.seen).
  - proc; wp; call visible_sign_budget; auto.
  - proc; wp; call visible_hash_budget; auto.
  auto.
qed.

local lemma visible_hash_lossless : islossless VisibleAccepted.h.
proof. proc; islossless. qed.

local lemma visible_hash_key_ll sk0 :
  phoare [VisibleAccepted.h : Programmed.sk=sk0 ==> Programmed.sk=sk0] = 1%r.
proof. by conseq visible_hash_lossless. qed.

local lemma visible_sign_key_ll sk0 : SD.check sk0 =>
  phoare [VisibleAccepted.sign : Programmed.sk=sk0 ==> Programmed.sk=sk0] = 1%r.
proof.
  move=> hsk; have hll := accepted_distribution_ll sk0 hsk.
  proc; sp; if.
  - by wp; rnd; auto => &hr />; smt().
  auto.
qed.

local lemma visible_romhash_ll sk0 :
  phoare [ROMHash(VisibleAccepted).get : Programmed.sk=sk0 ==> Programmed.sk=sk0] = 1%r.
proof. proc; call (visible_hash_key_ll sk0); auto. qed.

local lemma visible_romsign_ll sk0 : SD.check sk0 =>
  phoare [ROMSign(VisibleAccepted).sign : Programmed.sk=sk0 ==> Programmed.sk=sk0] = 1%r.
proof. move=> hsk; proc; wp; call (visible_sign_key_ll sk0 hsk); auto. qed.

local lemma original_visible_ll sk0 : SD.check sk0 =>
  phoare [A(ROMHash(VisibleAccepted),
    SD.CG.OCR(ROMHash(VisibleAccepted),ROMSign(VisibleAccepted))).forge :
    Programmed.sk=sk0 ==> Programmed.sk=sk0] = 1%r.
proof.
  move=> hsk; proc (Programmed.sk=sk0) => //.
  - move=> H' O' hs hh; exact (A_ll O' H' hs hh).
  - proc; wp; call (visible_romhash_ll sk0); wp; call (visible_romsign_ll sk0 hsk); auto.
  - exact (visible_romhash_ll sk0).
qed.

local lemma converted_visible_ll sk0 : SD.check sk0 =>
  phoare [SD.CG.RedFSaG(RedS(A),ROMHash(VisibleAccepted),ROMSign(VisibleAccepted)).forge :
    Programmed.sk=sk0 ==> Programmed.sk=sk0] = 1%r.
proof.
  move=> hsk; proc; inline *; wp; call (original_visible_ll sk0 hsk); auto.
qed.

local lemma rom_visible_ll sk0 : SD.check sk0 =>
  phoare [ROMAdversary(SD.CG.RedFSaG(RedS(A)),VisibleAccepted).distinguish :
    Programmed.sk=sk0 ==> Programmed.sk=sk0] = 1%r.
proof.
  move=> hsk; proc; wp; call (visible_hash_key_ll sk0); wp.
  call (converted_visible_ll sk0 hsk); auto.
qed.

local lemma visible_batch_ll pk sk &m : SD.check sk =>
  Pr[VisibleBatchGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : true]=1%r.
proof.
  move=> hsk; byphoare (_ : arg=(pk,sk) ==> true) => //.
  proc; call (rom_visible_ll sk hsk); call (failed_batch_lossless sk qS hsk).
  inline Programmed.init; auto.
qed.

lemma accepted_draw_components sk x : x \in accepted_distribution sk =>
  (oget (trial_transcript sk x)).`1=x.`1.`1 /\
  (oget (trial_transcript sk x)).`2=x.`2.
proof.
  rewrite /accepted_distribution dcond_supp /predC /trial_reject.
  move=> [_ hn]; rewrite /trial_transcript.
  by case: (SD.respond sk x.`2 x.`1.`2) hn => [|z] //=.
qed.

local lemma accepted_visible_hash : equiv
  [AcceptedOnly.h ~ VisibleAccepted.h :
    ={arg,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH} ==>
    ={res,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH}].
proof.
  proc; inline *; sp; if; first by move=> &1 &2 />.
  - auto; rewrite /cached_value; move=> &1 &2 /> hcap c hc.
    case (FMap.dom Programmed.table{2} (w{2},msg{2})) => hd.
    + rewrite /= (FMap.set_get Programmed.table{2} (w{2},msg{2}) hd); smt().
    rewrite /= FMap.get_set_sameE /=; smt().
  auto.
qed.

local lemma accepted_visible_sign sk0 : SD.check sk0 =>
  equiv [AcceptedOnly.sign ~ VisibleAccepted.sign :
    ={arg,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH} /\
    Programmed.sk{1}=sk0 ==>
    ={res,Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH}].
proof.
  move=> hsk; proc; sp; if; first by move=> &1 &2 />.
  - transitivity* {2} {
      sig <@ AcceptedDraw.run(Programmed.sk);
      Programmed.table <- FMap."_.[_<-_]" Programmed.table (sig.`1,msg) sig.`2;
      Programmed.countS <- Programmed.countS+1;
    }.
    + wp; call (accepted_draw_correct sk0 hsk); auto => &1 &2 />; smt().
    inline AcceptedDraw.run; wp; rnd; auto => &1 &2 />.
    move=> x hx; have hh := accepted_draw_components Programmed.sk{2} x hx; smt().
  auto; rewrite oget_none; smt().
qed.

local module VisibleScoreGame (B : SD.FSaG.DSS.Adv_EFCMA_RO) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r;
    Programmed.init(sk);
    RejectMonitor.seen <- [];
    r <@ ROMAdversary(B,VisibleAccepted).distinguish(pk);
    return r;
  }
}.

local lemma accepted_visible_score
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-RejectMonitor}) sk0 :
  SD.check sk0 =>
  equiv [AcceptedOnlyGame(B).main ~ VisibleScoreGame(B).main :
    ={arg,glob B} /\ arg{1}.`2=sk0 ==> ={res}].
proof.
  move=> hsk; proc; call (_ : ={arg,glob B,Programmed.sk,Programmed.table,
    Programmed.countS,Programmed.countH} /\ Programmed.sk{1}=sk0 ==> ={res}).
  - proc; wp; call accepted_visible_hash; wp.
    call (_ : ={Programmed.sk,Programmed.table,Programmed.countS,Programmed.countH,ROMSign.qs} /\
      Programmed.sk{1}=sk0).
    + proc; wp; call (accepted_visible_sign sk0 hsk); auto.
    + proc; wp; call accepted_visible_hash; auto.
    auto.
  inline Programmed.init; auto.
qed.

local lemma visible_batch_score
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-ROMSign,-RejectMonitor}) sk0 :
  SD.check sk0 =>
  equiv [VisibleBatchGame(B).main ~ VisibleScoreGame(B).main :
    ={arg,glob B} /\ arg{1}.`2=sk0 ==> res{1}.`1=res{2}].
proof.
  move=> hsk; proc; wp.
  call (_ : ={arg,glob B,glob Programmed,RejectMonitor.seen} ==> ={res}); first by sim.
  call{1} (failed_batch_lossless sk0 qS hsk).
  inline Programmed.init; auto.
qed.

local lemma deferred_bad_bound pk sk &m : SD.check sk =>
  Pr[DeferredBatchGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res.`2] <= hidden_budget sk.
proof.
  move=> hsk; byphoare (_ : arg=(pk,sk) ==> res.`2) => //.
  proc; wp; call (check_batch_bound sk hsk).
  call (visible_adversary_budget (SD.CG.RedFSaG(RedS(A)))).
  inline Programmed.init; auto; rewrite /visible_budget_inv /external_budget /=;
    smt(qS_ge0 qH_ge0).
qed.

local lemma preloaded_visible_ll pk sk &m : SD.check sk =>
  Pr[PreloadedMonitoredGame(SD.CG.RedFSaG(RedS(A)),VisibleHashPolicy).main(pk,sk) @ &m : true]=1%r.
proof.
  move=> hsk.
  have he : Pr[PreloadedMonitoredGame(SD.CG.RedFSaG(RedS(A)),VisibleHashPolicy).main(pk,sk) @ &m : true] =
    Pr[VisibleBatchGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : true].
  - byequiv (preloaded_visible_batch (SD.CG.RedFSaG(RedS(A)))) => //.
  rewrite he; exact (visible_batch_ll pk sk &m hsk).
qed.

local lemma preloaded_visible_score pk sk &m : SD.check sk =>
  Pr[PreloadedMonitoredGame(SD.CG.RedFSaG(RedS(A)),VisibleHashPolicy).main(pk,sk) @ &m : res] =
  Pr[AcceptedOnlyGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res].
proof.
  move=> hsk.
  have h1 : Pr[PreloadedMonitoredGame(SD.CG.RedFSaG(RedS(A)),VisibleHashPolicy).main(pk,sk) @ &m : res] =
    Pr[VisibleBatchGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res.`1].
  - byequiv (preloaded_visible_batch (SD.CG.RedFSaG(RedS(A)))) => //.
  have h2 : Pr[VisibleBatchGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res.`1] =
    Pr[VisibleScoreGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res].
  - byequiv (visible_batch_score (SD.CG.RedFSaG(RedS(A))) sk hsk) => //.
  have h3 : Pr[AcceptedOnlyGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res] =
    Pr[VisibleScoreGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res].
  - byequiv (accepted_visible_score (SD.CG.RedFSaG(RedS(A))) sk hsk) => //.
  by rewrite h1 h2 h3.
qed.

local lemma preloaded_visible_bad pk sk &m : SD.check sk =>
  Pr[PreloadedMonitoredGame(SD.CG.RedFSaG(RedS(A)),VisibleHashPolicy).main(pk,sk) @ &m : RejectMonitor.bad] <= hidden_budget sk.
proof.
  move=> hsk.
  have h1 : Pr[PreloadedMonitoredGame(SD.CG.RedFSaG(RedS(A)),VisibleHashPolicy).main(pk,sk) @ &m : RejectMonitor.bad] =
    Pr[VisibleBatchGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res.`2].
  - byequiv (preloaded_visible_batch (SD.CG.RedFSaG(RedS(A)))) => //.
  have h2 : Pr[VisibleBatchGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res.`2] =
    Pr[DeferredBatchGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res.`2].
  - byequiv (visible_batch_deferred (SD.CG.RedFSaG(RedS(A)))) => //.
  rewrite h1 h2; exact (deferred_bad_bound pk sk &m hsk).
qed.

local lemma hidden_full_visible_hop
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-HiddenLogs,-RejectMonitor}) pk sk &m :
  Pr[PreloadedMonitoredGame(B,VisibleHashPolicy).main(pk,sk) @ &m : true]=1%r =>
  Pr[PreloadedMonitoredGame(B,FullHashPolicy).main(pk,sk) @ &m : res] <=
  Pr[PreloadedMonitoredGame(B,VisibleHashPolicy).main(pk,sk) @ &m : res] +
  Pr[PreloadedMonitoredGame(B,VisibleHashPolicy).main(pk,sk) @ &m : RejectMonitor.bad].
proof.
  move=> hll; have he := hidden_hash_upto B pk sk &m.
  have hn := hidden_hash_nonbad B pk sk &m.
  move: hn; rewrite Pr[mu_not] Pr[mu_not] hll; move=> hn.
  have ht : Pr[PreloadedMonitoredGame(B,FullHashPolicy).main(pk,sk) @ &m : true]<=1%r.
  - by rewrite Pr[mu_le1].
  have hs : Pr[PreloadedMonitoredGame(B,FullHashPolicy).main(pk,sk) @ &m : res] =
    Pr[PreloadedMonitoredGame(B,FullHashPolicy).main(pk,sk) @ &m : res /\ !RejectMonitor.bad] +
    Pr[PreloadedMonitoredGame(B,FullHashPolicy).main(pk,sk) @ &m : res /\ RejectMonitor.bad].
  - by rewrite Pr[mu_split !RejectMonitor.bad] /=.
  have h1 : Pr[PreloadedMonitoredGame(B,FullHashPolicy).main(pk,sk) @ &m : res /\ RejectMonitor.bad] <=
    Pr[PreloadedMonitoredGame(B,FullHashPolicy).main(pk,sk) @ &m : RejectMonitor.bad].
  - by rewrite Pr[mu_sub]; smt().
  have h2 : Pr[PreloadedMonitoredGame(B,VisibleHashPolicy).main(pk,sk) @ &m : res /\ !RejectMonitor.bad] <=
    Pr[PreloadedMonitoredGame(B,VisibleHashPolicy).main(pk,sk) @ &m : res].
  - by rewrite Pr[mu_sub]; smt().
  smt().
qed.

local lemma eager_to_accepted pk sk &m : SD.check sk =>
  Pr[EagerLoggedGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res] <=
  Pr[AcceptedOnlyGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res] + hidden_budget sk.
proof.
  move=> hsk.
  have he : Pr[EagerLoggedGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res] =
    Pr[PreloadedMonitoredGame(SD.CG.RedFSaG(RedS(A)),FullHashPolicy).main(pk,sk) @ &m : res].
  - byequiv (eager_preloaded_full (SD.CG.RedFSaG(RedS(A)))) => //.
  have hh := hidden_full_visible_hop (SD.CG.RedFSaG(RedS(A))) pk sk &m
    (preloaded_visible_ll pk sk &m hsk).
  have hb := preloaded_visible_bad pk sk &m hsk.
  rewrite -he (preloaded_visible_score pk sk &m hsk) in hh; smt().
qed.

lemma reduction_algebra (a b c t h e k0 : real) :
  a<=b+t => b<=c+h => t+h=e*k0 => a<=c+k0*e.
proof. smt(). qed.

local lemma real_to_simulated pk sk &m :
  (pk,sk) \in SD.keygen => SD.check sk =>
  Pr[RealCMAFixed(SD.CG.RedFSaG(RedS(A))).run(pk,sk) @ &m : res] <=
  Pr[SimulatedOnlyGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res] +
    rom_coefficient*p_max (dfst (SD.commit sk)).
proof.
  move=> hkey hsk; have h0 := real_to_eager pk sk &m hsk.
  have h1 := eager_to_accepted pk sk &m hsk.
  have he : Pr[AcceptedOnlyGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res] =
    Pr[SimulatedOnlyGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res].
  - byequiv (accepted_simulated_game (SD.CG.RedFSaG(RedS(A))) pk sk hkey) => //.
  have hc := rom_cost_assembly (p_max (dfst (SD.commit sk))).
  move: h1; rewrite he /hidden_budget; move=> h1.
  exact (reduction_algebra _ _ _ _ _ _ _ h0 h1 hc).
qed.

local module CoreGateGame (B : SD.FSaG.DSS.Adv_EFCMA_RO)
  (Core : SD.CMAtoKOA.R1.Oracle) (Excess : SD.CMAtoKOA.R1.Oracle) = {
  proc main(pk : SD.PK) = {
    var r;
    SD.CMAtoKOA.CountH.qh <- 0;
    SD.CMAtoKOA.CountS.qs <- 0;
    r <@ ROMAdversary(B,CapOracle(Core,Excess)).distinguish(pk);
    return r;
  }
}.

local lemma core_gate_last_budget
  (Core <: SD.CMAtoKOA.R1.Oracle {-A,-ROMSign,-CapMonitor,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS})
  (Excess <: SD.CMAtoKOA.R1.Oracle {-A,-ROMSign,-CapMonitor,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [CapOracle(Core,Excess).h :
    SD.CMAtoKOA.CountH.qh<=qH+qS /\ SD.CMAtoKOA.CountS.qs<=qS ==>
    SD.CMAtoKOA.CountH.qh<=external_budget /\ SD.CMAtoKOA.CountS.qs<=qS].
proof.
  proc; inline MarkedExcess(Excess).h; sp; if; wp; call (_ : true); auto;
    rewrite /external_budget; smt().
qed.

local lemma core_gate_query_bound
  (Core <: SD.CMAtoKOA.R1.Oracle {-A,-ROMSign,-CapMonitor,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS})
  (Excess <: SD.CMAtoKOA.R1.Oracle {-A,-ROMSign,-CapMonitor,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [CoreGateGame(SD.CG.RedFSaG(RedS(A)),Core,Excess).main : true ==>
    SD.CMAtoKOA.CountH.qh<=external_budget /\ SD.CMAtoKOA.CountS.qs<=qS].
proof.
  proc; inline ROMAdversary(SD.CG.RedFSaG(RedS(A)),CapOracle(Core,Excess)).distinguish.
  wp; call (core_gate_last_budget Core Excess); wp.
  call (gate_recorded_budget (CapBranches(Core,Excess))); auto.
qed.

local lemma core_gate_hash_overflow
  (Core <: SD.CMAtoKOA.R1.Oracle {-CapMonitor,-SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS})
  (Excess <: SD.CMAtoKOA.R1.Oracle {-CapMonitor,-SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [CapOracle(Core,Excess).h :
    CapMonitor.bad => cap_overflow SD.CMAtoKOA.CountH.qh SD.CMAtoKOA.CountS.qs ==>
    CapMonitor.bad => cap_overflow SD.CMAtoKOA.CountH.qh SD.CMAtoKOA.CountS.qs].
proof.
  proc; inline MarkedExcess(Excess).h; sp; if; wp; call (_ : true); auto;
    rewrite /cap_overflow; smt().
qed.

local lemma core_gate_sign_overflow
  (Core <: SD.CMAtoKOA.R1.Oracle {-CapMonitor,-SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS})
  (Excess <: SD.CMAtoKOA.R1.Oracle {-CapMonitor,-SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [CapOracle(Core,Excess).sign :
    CapMonitor.bad => cap_overflow SD.CMAtoKOA.CountH.qh SD.CMAtoKOA.CountS.qs ==>
    CapMonitor.bad => cap_overflow SD.CMAtoKOA.CountH.qh SD.CMAtoKOA.CountS.qs].
proof.
  proc; inline MarkedExcess(Excess).sign; sp; if; wp; call (_ : true); auto;
    rewrite /cap_overflow; smt().
qed.

local lemma core_gate_overflow
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-CapMonitor,-SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS})
  (Core <: SD.CMAtoKOA.R1.Oracle {-CapMonitor,-SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS})
  (Excess <: SD.CMAtoKOA.R1.Oracle {-CapMonitor,-SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [CoreGateGame(B,Core,Excess).main : !CapMonitor.bad ==>
    CapMonitor.bad => cap_overflow SD.CMAtoKOA.CountH.qh SD.CMAtoKOA.CountS.qs].
proof.
  proc; inline ROMAdversary(B,CapOracle(Core,Excess)).distinguish.
  wp; call (core_gate_hash_overflow Core Excess); wp.
  call (_ : CapMonitor.bad => cap_overflow SD.CMAtoKOA.CountH.qh SD.CMAtoKOA.CountS.qs).
  - proc; wp; call (core_gate_sign_overflow Core Excess); auto.
  - proc; wp; call (core_gate_hash_overflow Core Excess); auto.
  auto.
qed.

local lemma core_gate_safe
  (Core <: SD.CMAtoKOA.R1.Oracle {-A,-ROMSign,-CapMonitor,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS})
  (Excess <: SD.CMAtoKOA.R1.Oracle {-A,-ROMSign,-CapMonitor,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [CoreGateGame(SD.CG.RedFSaG(RedS(A)),Core,Excess).main : !CapMonitor.bad ==> !CapMonitor.bad].
proof.
  conseq (core_gate_query_bound Core Excess)
    (core_gate_overflow (SD.CG.RedFSaG(RedS(A))) Core Excess);
    rewrite /cap_overflow; smt().
qed.

local module SimCore = {
  import var Programmed
  proc h = RawCore.h
  proc sign(msg : M) = {
    var w,c,z;
    (w,c,z) <@ SimTranscriptLoop.run(SimulatedOnly.pk);
    table <- FMap."_.[_<-_]" table (w,msg) c;
    return (w,c,z);
  }
}.

local module SimGated (B : SD.FSaG.DSS.Adv_EFCMA_RO)
  (Excess : SD.CMAtoKOA.R1.Oracle) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r;
    SimulatedOnly.init(pk,sk);
    CapMonitor.bad <- false;
    r <@ CoreGateGame(B,SimCore,Excess).main(pk);
    return r;
  }
}.

local module UncappedSimGame (B : SD.FSaG.DSS.Adv_EFCMA_RO) = {
  proc main(pk : SD.PK, sk : SD.SK) = {
    var r;
    SimulatedOnly.init(pk,sk);
    r <@ ROMAdversary(B,SimCore).distinguish(pk);
    return r;
  }
}.

local lemma sim_gated_safe
  (Excess <: SD.CMAtoKOA.R1.Oracle {-A,-ROMSign,-CapMonitor,-SD.CountH,-SD.CountS,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  hoare [SimGated(SD.CG.RedFSaG(RedS(A)),Excess).main : true ==> !CapMonitor.bad].
proof.
  proc; call (core_gate_safe SimCore Excess); inline SimulatedOnly.init Programmed.init; auto.
qed.

local lemma sim_gated_upto pk sk &m :
  Pr[SimGated(SD.CG.RedFSaG(RedS(A)),SimCore).main(pk,sk) @ &m : res /\ !CapMonitor.bad] =
  Pr[SimGated(SD.CG.RedFSaG(RedS(A)),NullOracle).main(pk,sk) @ &m : res /\ !CapMonitor.bad].
proof. byupto. qed.

local lemma sim_cap_pass_hash : equiv
  [CapOracle(SimCore,SimCore).h ~ SimCore.h :
    ={arg,Programmed.sk,Programmed.table,SimulatedOnly.pk} ==>
    ={res,Programmed.sk,Programmed.table,SimulatedOnly.pk}].
proof. proc; inline *; sp; if{1}; auto. qed.

local lemma sim_cap_pass_sign : equiv
  [CapOracle(SimCore,SimCore).sign ~ SimCore.sign :
    ={arg,Programmed.sk,Programmed.table,SimulatedOnly.pk} ==>
    ={res,Programmed.sk,Programmed.table,SimulatedOnly.pk}].
proof.
  proc; inline MarkedExcess(SimCore).sign SimCore.sign; sp; if{1}.
  - wp; call (_ : true); first by sim.
    auto.
  wp; call (_ : true); first by sim.
  auto.
qed.

local lemma sim_cap_pass_adversary
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-SimulatedOnly,-ROMSign,-CapMonitor,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  equiv [ROMAdversary(B,CapOracle(SimCore,SimCore)).distinguish ~
    ROMAdversary(B,SimCore).distinguish :
    ={arg,glob B,Programmed.sk,Programmed.table,SimulatedOnly.pk} ==> ={res}].
proof.
  proc; wp; call sim_cap_pass_hash; wp.
  call (_ : ={Programmed.sk,Programmed.table,SimulatedOnly.pk,ROMSign.qs}).
  - proc; wp; call sim_cap_pass_sign; auto.
  - proc; wp; call sim_cap_pass_hash; auto.
  auto.
qed.

local lemma sim_cap_pass_game
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-SimulatedOnly,-ROMSign,-CapMonitor,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  equiv [SimGated(B,SimCore).main ~ UncappedSimGame(B).main :
    ={arg,glob B} ==> ={res}].
proof.
  proc; inline CoreGateGame(B,SimCore,SimCore).main; wp;
    call (sim_cap_pass_adversary B); inline SimulatedOnly.init Programmed.init; auto.
qed.

local lemma sim_cap_null_hash : equiv
  [CapOracle(SimCore,NullOracle).h ~ SimulatedOnly.h :
    ={arg,SimulatedOnly.pk} /\ cap_raw_state Programmed.sk{1} Programmed.sk{2}
      Programmed.table{1} Programmed.table{2}
      SD.CMAtoKOA.CountH.qh{1} SD.CMAtoKOA.CountS.qs{1}
      Programmed.countH{2} Programmed.countS{2} ==>
    ={res,SimulatedOnly.pk} /\ cap_raw_state Programmed.sk{1} Programmed.sk{2}
      Programmed.table{1} Programmed.table{2}
      SD.CMAtoKOA.CountH.qh{1} SD.CMAtoKOA.CountS.qs{1}
      Programmed.countH{2} Programmed.countS{2}].
proof.
  proc; inline *; sp; if.
  - rewrite /cap_raw_state; smt(bounded_count_guard).
  - auto; rewrite /cap_raw_state; smt(bounded_count_step).
  auto; rewrite /cap_raw_state; smt(bounded_count_step).
qed.

local lemma sim_cap_null_sign : equiv
  [CapOracle(SimCore,NullOracle).sign ~ SimulatedOnly.sign :
    ={arg,SimulatedOnly.pk} /\ cap_raw_state Programmed.sk{1} Programmed.sk{2}
      Programmed.table{1} Programmed.table{2}
      SD.CMAtoKOA.CountH.qh{1} SD.CMAtoKOA.CountS.qs{1}
      Programmed.countH{2} Programmed.countS{2} ==>
    ={res,SimulatedOnly.pk} /\ cap_raw_state Programmed.sk{1} Programmed.sk{2}
      Programmed.table{1} Programmed.table{2}
      SD.CMAtoKOA.CountH.qh{1} SD.CMAtoKOA.CountS.qs{1}
      Programmed.countH{2} Programmed.countS{2}].
proof.
  proc; inline MarkedExcess(NullOracle).sign NullOracle.sign SimCore.sign; sp; if.
  - rewrite /cap_raw_state; smt(bounded_count_guard).
  - wp; call (_ : true); first by sim.
    auto; rewrite /cap_raw_state; smt(bounded_count_step).
  auto; rewrite /cap_raw_state oget_none; smt(bounded_count_step).
qed.

local lemma sim_gated_no_overflow pk sk &m :
  Pr[SimGated(SD.CG.RedFSaG(RedS(A)),SimCore).main(pk,sk) @ &m : res] =
  Pr[SimGated(SD.CG.RedFSaG(RedS(A)),NullOracle).main(pk,sk) @ &m : res].
proof.
  have hl : Pr[SimGated(SD.CG.RedFSaG(RedS(A)),SimCore).main(pk,sk) @ &m : res] =
    Pr[SimGated(SD.CG.RedFSaG(RedS(A)),SimCore).main(pk,sk) @ &m : res /\ !CapMonitor.bad].
  - byequiv (_ : ={arg,glob A} ==> ={res} /\ !CapMonitor.bad{2}) => //.
    conseq (_ : _ ==> ={res}) _ (sim_gated_safe SimCore); sim.
  have hr : Pr[SimGated(SD.CG.RedFSaG(RedS(A)),NullOracle).main(pk,sk) @ &m : res] =
    Pr[SimGated(SD.CG.RedFSaG(RedS(A)),NullOracle).main(pk,sk) @ &m : res /\ !CapMonitor.bad].
  - byequiv (_ : ={arg,glob A} ==> ={res} /\ !CapMonitor.bad{2}) => //.
    conseq (_ : _ ==> ={res}) _ (sim_gated_safe NullOracle); sim.
  rewrite hl hr; exact (sim_gated_upto pk sk &m).
qed.

local lemma sim_cap_null_adversary
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-SimulatedOnly,-ROMSign,-CapMonitor,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  equiv [ROMAdversary(B,CapOracle(SimCore,NullOracle)).distinguish ~
    ROMAdversary(B,SimulatedOnly).distinguish :
    ={arg,glob B,SimulatedOnly.pk} /\ cap_raw_state Programmed.sk{1} Programmed.sk{2}
      Programmed.table{1} Programmed.table{2}
      SD.CMAtoKOA.CountH.qh{1} SD.CMAtoKOA.CountS.qs{1}
      Programmed.countH{2} Programmed.countS{2} ==> ={res}].
proof.
  proc; wp; call sim_cap_null_hash; wp.
  call (_ : ={ROMSign.qs,SimulatedOnly.pk} /\ cap_raw_state Programmed.sk{1} Programmed.sk{2}
      Programmed.table{1} Programmed.table{2}
      SD.CMAtoKOA.CountH.qh{1} SD.CMAtoKOA.CountS.qs{1}
      Programmed.countH{2} Programmed.countS{2}).
  - proc; wp; call sim_cap_null_sign; auto.
  - proc; wp; call sim_cap_null_hash; auto.
  auto.
qed.

local lemma sim_cap_null_game
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-SimulatedOnly,-ROMSign,-CapMonitor,
    -SD.CMAtoKOA.CountH,-SD.CMAtoKOA.CountS}) :
  equiv [SimGated(B,NullOracle).main ~ SimulatedOnlyGame(B).main :
    ={arg,glob B} ==> ={res}].
proof.
  proc; inline CoreGateGame(B,SimCore,NullOracle).main; wp;
    call (sim_cap_null_adversary B); inline SimulatedOnly.init Programmed.init; auto.
  rewrite /cap_raw_state /bounded_count /external_budget; smt(qS_ge0 qH_ge0).
qed.

local lemma simulated_uncapped pk sk &m :
  Pr[SimulatedOnlyGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res] =
  Pr[UncappedSimGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res].
proof.
  have he : Pr[SimGated(SD.CG.RedFSaG(RedS(A)),NullOracle).main(pk,sk) @ &m : res] =
    Pr[SimulatedOnlyGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res].
  - byequiv (sim_cap_null_game (SD.CG.RedFSaG(RedS(A)))) => //.
  rewrite -he -(sim_gated_no_overflow pk sk &m).
  byequiv (sim_cap_pass_game (SD.CG.RedFSaG(RedS(A)))) => //.
qed.

op overlay_tables (full base overlay : (high list*M,Rq) FMap.fmap) =
  forall key, FMap."_.[_]" full key =
    if FMap."_.[_]" overlay key=None then FMap."_.[_]" base key
    else FMap."_.[_]" overlay key.

op overlay_signed (overlay : (high list*M,Rq) FMap.fmap) (qs : M list) =
  forall key, FMap."_.[_]" overlay key<>None => key.`2 \in qs.

lemma overlay_tables_empty : overlay_tables FMap.empty FMap.empty FMap.empty.
proof. by rewrite /overlay_tables; move=> key; rewrite FMap.emptyE. qed.

lemma overlay_tables_program full base overlay key c :
  overlay_tables full base overlay =>
  overlay_tables (FMap."_.[_<-_]" full key c) base
    (FMap."_.[_<-_]" overlay key c).
proof.
  rewrite /overlay_tables; move=> hm key0.
  rewrite !FMap.get_setE; case (key0=key) => he /=; first by [].
  exact (hm key0).
qed.

lemma overlay_tables_base full base overlay key c :
  overlay_tables full base overlay => FMap."_.[_]" overlay key=None =>
  overlay_tables (FMap."_.[_<-_]" full key c)
    (FMap."_.[_<-_]" base key c) overlay.
proof.
  rewrite /overlay_tables; move=> hm ho key0.
  rewrite !FMap.get_setE; case (key0=key) => he /=.
  - by rewrite he ho.
  exact (hm key0).
qed.

lemma overlay_signed_program overlay qs w msg c :
  overlay_signed overlay qs =>
  overlay_signed (FMap."_.[_<-_]" overlay (w,msg) c) (rcons qs msg).
proof.
  rewrite /overlay_signed; move=> hs key.
  rewrite FMap.get_setE mem_rcons; case (key=(w,msg)) => he /=.
  - by rewrite he /=.
  smt().
qed.

lemma overlay_signed_set overlay qs w msg c :
  overlay_signed overlay qs => msg \in qs =>
  overlay_signed (FMap."_.[_<-_]" overlay (w,msg) c) qs.
proof.
  rewrite /overlay_signed; move=> hs hm key.
  rewrite FMap.get_setE; case (key=(w,msg)) => he /=.
  - by rewrite he /=.
  exact (hs key).
qed.

local module FixedKeyKOA = {
  proc run(ks : SD.PK*SD.SK) = {
    var msg,sig,w,z,c;
    SD.RO_G.init();
    (msg,sig) <@ FixedKOA(SD.RO_G).forge(ks.`1);
    (w,z) <- sig;
    c <@ SD.RO_G.get(w,msg);
    return SD.verify ks.`1 w c z;
  }
}.

local lemma sim_overlay_hash : equiv
  [ROMHash(SimCore).get ~ SD.CMAtoKOA.RedKOA_H'(SD.RO_G).get :
    ={arg} /\ overlay_tables Programmed.table{1} SD.RO_G.m{2}
      SD.CMAtoKOA.ORedKOA.overlay{2} ==>
    ={res} /\ overlay_tables Programmed.table{1} SD.RO_G.m{2}
      SD.CMAtoKOA.ORedKOA.overlay{2}].
proof.
  proc; inline SimCore.h; sp; if{2}.
  - inline SD.RO_G.get; auto => &1 &2 /> hm ho c hc.
    have hk := hm x{2}; move: hk; rewrite ho /=; move=> hk.
    have hu := overlay_tables_base Programmed.table{1} SD.RO_G.m{2}
      SD.CMAtoKOA.ORedKOA.overlay{2} x{2} c hm ho.
    have hx : (x{2}.`1,x{2}.`2)=x{2} by case: (x{2}) => a b.
    rewrite hx /FMap.dom hk !FMap.get_set_sameE /=.
    smt().
  wp; rnd{1}; auto => &1 &2 /> hm ho.
  move=> c hc; have hk := hm x{2}; move: hk; rewrite ho /=; move=> hk.
  have hx : (x{2}.`1,x{2}.`2)=x{2} by case: (x{2}) => a b.
  rewrite hx /FMap.dom hk ho /=; smt().
qed.

local lemma sim_overlay_sign : equiv
  [ROMSign(SimCore).sign ~ SD.CMAtoKOA.ORedKOA(SD.HVZK_Sim_Inst).sign :
    ={arg} /\ SimulatedOnly.pk{1}=SD.CMAtoKOA.ORedKOA.pk{2} /\
    ROMSign.qs{1}=SD.CMAtoKOA.ORedKOA.qs{2} /\
    overlay_tables Programmed.table{1} SD.RO_G.m{2} SD.CMAtoKOA.ORedKOA.overlay{2} /\
    overlay_signed SD.CMAtoKOA.ORedKOA.overlay{2} SD.CMAtoKOA.ORedKOA.qs{2} ==>
    ={res} /\ SimulatedOnly.pk{1}=SD.CMAtoKOA.ORedKOA.pk{2} /\
    ROMSign.qs{1}=SD.CMAtoKOA.ORedKOA.qs{2} /\
    overlay_tables Programmed.table{1} SD.RO_G.m{2} SD.CMAtoKOA.ORedKOA.overlay{2} /\
    overlay_signed SD.CMAtoKOA.ORedKOA.overlay{2} SD.CMAtoKOA.ORedKOA.qs{2}].
proof.
  proc; inline SimCore.sign SimTranscriptLoop.run; wp.
  while (={ot} /\ msg{1}=m{2} /\
    m{2} \in SD.CMAtoKOA.ORedKOA.qs{2} /\
    pk{1}=SD.CMAtoKOA.ORedKOA.pk{2} /\
    SimulatedOnly.pk{1}=SD.CMAtoKOA.ORedKOA.pk{2} /\
    ROMSign.qs{1}=SD.CMAtoKOA.ORedKOA.qs{2} /\
    overlay_tables Programmed.table{1} SD.RO_G.m{2} SD.CMAtoKOA.ORedKOA.overlay{2} /\
    (forall key, FMap."_.[_]" SD.CMAtoKOA.ORedKOA.overlay{2} key<>None =>
      key.`2 \in SD.CMAtoKOA.ORedKOA.qs{2})).
  - call (_ : true); first by sim.
    auto.
  auto; rewrite /overlay_signed; move=> &1 &2 />.
  move=> hm hs; split.
  - split; first by rewrite mem_rcons /=.
    move=> key hk; rewrite mem_rcons; right; exact (hs key hk).
  move=> ot hn hn0 hmsg hqs; split.
  - exact (overlay_tables_program _ _ _ _ _ hm).
  exact (overlay_signed_set _ _ _ _ _ hqs hmsg).
qed.

local lemma sim_overlay_forge
  (B <: SD.FSaG.DSS.Adv_EFCMA_RO {-Programmed,-SimulatedOnly,-ROMSign,
    -SD.RO_G,-SD.CMAtoKOA.ORedKOA}) :
  equiv [B(ROMHash(SimCore),ROMSign(SimCore)).forge ~
    B(SD.CMAtoKOA.RedKOA_H'(SD.RO_G),SD.CMAtoKOA.ORedKOA(SD.HVZK_Sim_Inst)).forge :
    ={arg,glob B} /\ SimulatedOnly.pk{1}=SD.CMAtoKOA.ORedKOA.pk{2} /\
    ROMSign.qs{1}=SD.CMAtoKOA.ORedKOA.qs{2} /\
    overlay_tables Programmed.table{1} SD.RO_G.m{2} SD.CMAtoKOA.ORedKOA.overlay{2} /\
    overlay_signed SD.CMAtoKOA.ORedKOA.overlay{2} SD.CMAtoKOA.ORedKOA.qs{2} ==>
    ={res} /\ SimulatedOnly.pk{1}=SD.CMAtoKOA.ORedKOA.pk{2} /\
    ROMSign.qs{1}=SD.CMAtoKOA.ORedKOA.qs{2} /\
    overlay_tables Programmed.table{1} SD.RO_G.m{2} SD.CMAtoKOA.ORedKOA.overlay{2} /\
    overlay_signed SD.CMAtoKOA.ORedKOA.overlay{2} SD.CMAtoKOA.ORedKOA.qs{2}].
proof.
  proc (SimulatedOnly.pk{1}=SD.CMAtoKOA.ORedKOA.pk{2} /\
    ROMSign.qs{1}=SD.CMAtoKOA.ORedKOA.qs{2} /\
    overlay_tables Programmed.table{1} SD.RO_G.m{2} SD.CMAtoKOA.ORedKOA.overlay{2} /\
    overlay_signed SD.CMAtoKOA.ORedKOA.overlay{2} SD.CMAtoKOA.ORedKOA.qs{2}) => //.
  - exact sim_overlay_sign.
  conseq sim_overlay_hash; smt().
qed.

local lemma sim_final_fresh_hash : equiv
  [SimCore.h ~ SD.RO_G.get :
    arg{1}=arg{2} /\
    overlay_tables Programmed.table{1} SD.RO_G.m{2} SD.CMAtoKOA.ORedKOA.overlay{2} /\
    FMap."_.[_]" SD.CMAtoKOA.ORedKOA.overlay{2} arg{2}=None ==> ={res}].
proof.
  proc; auto => &1 &2 /> hm ho c hc.
  have hk := hm (w{1},msg{1}); move: hk; rewrite ho /=; move=> hk.
  rewrite /FMap.dom hk !FMap.get_set_sameE /=; smt().
qed.

local lemma sim_core_hash_ll : islossless SimCore.h.
proof. proc; islossless. qed.

local lemma fixed_koa_hash_ll : islossless SD.RO_G.get.
proof. proc; islossless. qed.

local lemma sim_final_hash key0 : equiv
  [SimCore.h ~ SD.RO_G.get :
    arg{1}=key0 /\ arg{2}=key0 /\
    overlay_tables Programmed.table{1} SD.RO_G.m{2} SD.CMAtoKOA.ORedKOA.overlay{2} /\
    overlay_signed SD.CMAtoKOA.ORedKOA.overlay{2} SD.CMAtoKOA.ORedKOA.qs{2} ==>
    !(key0.`2 \in SD.CMAtoKOA.ORedKOA.qs{2}) => ={res}].
proof.
  proc*; case (key0.`2 \in SD.CMAtoKOA.ORedKOA.qs{2}).
  - inline SimCore.h SD.RO_G.get; auto.
  call sim_final_fresh_hash; auto; rewrite /overlay_signed; smt().
qed.

local lemma uncapped_to_koa pk sk &m :
  Pr[UncappedSimGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res] <=
  Pr[FixedKeyKOA.run(pk,sk) @ &m : res].
proof.
  byequiv (_ : arg{1}=arg{2} /\ ={glob A} ==> res{1}=>res{2}) => //.
  proc; inline ROMAdversary(SD.CG.RedFSaG(RedS(A)),SimCore).distinguish
    FixedKOA(SD.RO_G).forge.
  wp.
  seq 5 6 : (pk0{1}=ks{2}.`1 /\ ={w,z,msg} /\
    ROMSign.qs{1}=SD.CMAtoKOA.ORedKOA.qs{2} /\
    overlay_tables Programmed.table{1} SD.RO_G.m{2} SD.CMAtoKOA.ORedKOA.overlay{2} /\
    overlay_signed SD.CMAtoKOA.ORedKOA.overlay{2} SD.CMAtoKOA.ORedKOA.qs{2}).
  - wp; call (sim_overlay_forge (SD.CG.RedFSaG(RedS(A)))).
    inline SimulatedOnly.init Programmed.init SD.RO_G.init
      SD.CMAtoKOA.ORedKOA(SD.HVZK_Sim_Inst).init.
    auto; rewrite /overlay_signed /overlay_tables ?FMap.emptyE /=;
      move=> &1 &2 />.
    move=> key; exact (FMap.emptyE key).
  exlim (w{1},msg{1}) => key0.
  call (sim_final_hash key0); auto => &1 &2 />; smt().
qed.

local lemma fixed_koa_average &m :
  Pr[SD.EF_KOA_RO_G(SD.OpBasedSigG,FixedKOA,SD.RO_G).main() @ &m : res] =
  E SD.keygen (fun ks => Pr[FixedKeyKOA.run(ks) @ &m : res]).
proof.
  rewrite -(key_average_probability FixedKeyKOA &m).
  byequiv (_ : ={glob A} ==> res{1}=res{2}.`2) => //.
  proc; inline *; wp; rnd; wp.
  call (_ : ={SD.RO_G.m,SD.CMAtoKOA.ORedKOA.pk,
    SD.CMAtoKOA.ORedKOA.qs,SD.CMAtoKOA.ORedKOA.overlay}).
  - by sim.
  - by sim.
  auto.
qed.

local lemma generic_rom_security &m :
  Pr[SD.EF_CMA_RO_G(SD.OpBasedSigG,SD.CG.RedFSaG(RedS(A)),SD.RO_G,
    SD.O_CMA_Default_G).main() @ &m : res] <=
  Pr[SD.EF_KOA_RO_G(SD.OpBasedSigG,FixedKOA,SD.RO_G).main() @ &m : res] +
    rom_coefficient*eps_comm+delta_.
proof.
  rewrite real_cma_average fixed_koa_average.
  apply average_security_bound; first exact rom_coefficient_ge0.
  - move=> ks /=; split.
    + split; [by rewrite Pr[mu_ge0] | by rewrite Pr[mu_le1]].
    by rewrite Pr[mu_ge0].
  move=> [pk sk] hkey hsk /=.
  have hr := real_to_simulated pk sk &m hkey hsk.
  move: hr; rewrite (simulated_uncapped pk sk &m); move=> hr.
  have hk := uncapped_to_koa pk sk &m.
  move: hr hk; clear.
  move: (Pr[RealCMAFixed(SD.CG.RedFSaG(RedS(A))).run(pk,sk) @ &m : res])
    (Pr[UncappedSimGame(SD.CG.RedFSaG(RedS(A))).main(pk,sk) @ &m : res])
    (Pr[FixedKeyKOA.run(pk,sk) @ &m : res]) => a b c.
  smt().
qed.

lemma security_assembly (a b c d t dlt : real) :
  a<=b => b<=c+t+dlt => c<=d => a<=d+t+dlt.
proof. smt(). qed.

  (* SCRATCHPAD END *)

lemma Dilithium_secure &m :
 Pr[EF_CMA_RO(Dilithium, A, H, O_CMA_Default).main() @ &m : res] <=
     `|Pr[MLWE_L(RedMLWE(A)).main() @ &m : res] -
       Pr[MLWE_R(RedMLWE(A)).main() @ &m : res]| +
     Pr[SelfTargetMSIS(RedStMSIS(A), SD.RqStMSIS.PRO.RO).main () @ &m : res] +
     (2%r * qS%r * (qH + qS + 1)%r * eps_comm / (1%r - p_rej) +
      qS%r * eps_comm * (qS%r + 1%r) / (2%r * (1%r - p_rej) ^ 2)) + delta_.
proof.
  rewrite (simplify_scheme &m) (operation_scheme &m) -rom_final_cost.
  exact (security_assembly _ _ _ _ _ _
    (cma_commitment_conversion &m) (generic_rom_security &m) (fixed_koa_lattice &m)).
qed.

end section PROOF.

end AbstractDilithium.

abstract theory ConcreteDilithium.

clone import DParams as Params.

clone import ConcreteDRing as CDR with
  op Round.q <= Params.q,
  op Round.n <= Params.n,
  axiom Round.prime_q <= Params.prime_q,
  axiom Round.gt0_n <= Params.gt0_n





.

clone import AbstractDilithium as ConcreteDilithium with
  theory Params <- Params,
  theory DR <- CDR.DR.

end ConcreteDilithium.
