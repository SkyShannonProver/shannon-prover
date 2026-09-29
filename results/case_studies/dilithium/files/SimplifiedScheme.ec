require import AllCore Distr List DistrExtras_port.

require import Finite DBool.

import Biased.

require DigitalSignaturesRO.

require MatPlus.

require import RealSeries Supplementary Finite.

require import IntDiv.

require import Nat.

require import IDSabort.

require FSabort.

require DRing DVect MLWE SelfTargetMSIS.

require DParams.

clone import DParams as Params.

const qS : int.

const qH : int.

axiom qS_ge0 : 0 <= qS.

axiom qH_ge0 : 0 <= qH.

clone import DRing as DR with
  op q <= q,
  op n <= n
proof prime_q by exact prime_q
proof gt0_n by exact gt0_n.

import RqRing.

clone import DVect as DV with
  theory DR <- DR,
  op HL.alpha <- 2*gamma2,
  op HL.d     <- d
proof HL.ge2_alpha, HL.alpha_halfq_le, HL.even_alpha, HL.alpha_almost_divides_q, HL.d_bound.

realize HL.ge2_alpha by smt(gamma2_bound).

realize HL.even_alpha by smt().

realize HL.alpha_halfq_le by smt(gamma2_bound).

realize HL.alpha_almost_divides_q by apply gamma2_div.

realize HL.d_bound.

split; 1: smt(gt0_d).

apply (StdOrder.IntOrder.ler_lt_trans (tau * 2 ^ d)).

smt(gt0_d tau_bound StdOrder.IntOrder.expr_gt0).

apply (StdOrder.IntOrder.ler_lt_trans (2 * gamma2) _ _ ub_d).

suff : `| 2 * gamma2 | <= `|Params.q -1| by smt(gamma2_bound prime_q gt1_prime).

by apply dvdz_le; smt(prime_q gt1_prime gamma2_div).

qed.

import DV.MatRq.

import DV.HL.

type M.

type challenge_t = Rq.

type SK = matrix * vector * vector.

type PK = matrix * vector.

type commit_t = high list.

type response_t = vector * hint_t list.

type pstate_t = vector.

clone IDS as DID with
  type PK <= PK,
  type SK <= SK,
  type W <= commit_t,
  type C <= challenge_t,
  type Z <= response_t,
  type Pstate <= pstate_t proof*.

clone import FSabort as FSa with
  type ID.PK <= PK,
  type ID.SK <= SK,
  type ID.W <= commit_t,
  type ID.C <= challenge_t,
  type ID.Z <= response_t,
  type ID.Pstate <= pstate_t,
  type M <= M,
  op dC <= dC tau
proof dC_ll by smt(dC_ll dC_uni tau_bound)
proof dC_uni by smt(dC_ll dC_uni tau_bound).

clone Generic as FSaG with
  op qS <= qS,
  op qH <= qH + Self.qS
proof qS_ge0 by smt(qS_ge0)
proof qH_ge0 by smt(qS_ge0 qH_ge0).

op recover (pk : PK) (c : challenge_t) (resp : response_t) : commit_t =
  let (mA, t) = pk in
  let (z, h) = resp in
  useHintV h (mA *^ z - c ** base2shiftV (base2highbitsV t)).

clone FSaG.CommRecov as FSaCR with
  op recover <= recover.

import FSaCR.

import FSaCR.DSS.

module (DilithiumS : SchemeRO)(H: Hash) = {
  proc keygen() : PK * SK = {
    var pk, sk;
    var mA, s1, s2,t;
    mA <$ dmatrix dRq k l;
    s1 <$ dvector (dRq_ Params.eta_) l;
    s2 <$ dvector (dRq_ Params.eta_) k;
    t  <- mA *^ s1 + s2;
    pk <- (mA, t);
    sk <- (mA, s1, s2);
    return (pk, sk);
  }

  proc sign(sk: SK, m: M) : Sig = {
    var z : vector;
    var h : hint_t list;
    var response : response_t option;
    var c : R;
    var ctr : int;
    var y, w, w1;
    var mA, s1, s2;
    var t0;

    c <- witness;

    (mA, s1, s2) <- sk;
    t0 <- base2lowbitsV (mA *^ s1 + s2);

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
    var mA, t, t1;
    var result;
    (mA, t) <- pk;
    t1 <- base2highbitsV t;

    (c, response) <- sig;
    (z, h) <- response;
    w1 <- useHintV h (mA *^ z - c ** base2shiftV t1);
    c' <@ H.get((w1, m));
    result <- size z = l /\ size h = k /\ inf_normv z < gamma1 - beta_ /\ c = c';

    return result;
  }
}.

clone import MLWE as RqMLWE with
  theory M <- MatRq,
  op dR <- dRq,
  op dS <- dRq_ Params.eta_,
  op k <- k,
  op l <- l
proof* by smt(gt0_k gt0_l).

clone import SelfTargetMSIS as RqStMSIS with
  theory M <- MatRq,
  type M <- M,
  op m <- k,
  op n <- l+1,
  op dR <- dRq,
  op dC <- dC tau,
  op inf_norm <- inf_normv,
  op gamma <- max (gamma1 - beta_) (tau * 2^(d-1) + (2*gamma2+1))
proof* by smt(gt0_k Params.gt0_l).

module H = DSS.PRO.RO.

module G = RqStMSIS.PRO.RO.

module RedMLWE (A : Adv_EFKOA_RO) (H : Hash_i) : RqMLWE.Adversary = {
  proc distinguish (mA : matrix, t : vector) = {
    var pk,m,sig,r;
    H.init();
    pk <- (mA,t);
    (m,sig) <@ A(H).forge(pk);
    r <@ DilithiumS(H).verify(pk,m,sig);
    return r;
  }
}.

module H' : Hash_i = {
  proc init = G.init

  proc get(w1,mu) = {
    var r;
    r <@ G.get(shiftV w1,mu);
    return r;
  }
}.

module RedMSIS (A : Adv_EFKOA_RO) (H : RqStMSIS.PRO.RO) = {
  proc guess(mB : matrix) : vector * M = {
    var mA,tbar,t,mu,sig,c,zh,z,h;
    var t1,r,u1,u2,y;
    mA <- subm mB 0 k 0 l;
    tbar <- col mB l;
    t <- -tbar;
    (mu,sig) <@ A(H').forge(mA,t);
    y <- witness;
    (c,zh) <- sig;
    (z,h) <- zh;
    t1 <- base2highbitsV t;
    r <- mA *^z - c ** base2shiftV t1;
    u1 <- r - shiftV (useHintV h r);
    u2 <- c ** base2lowbitsV t;
    y <- (u2 - u1) || z || vectc 1 c;

    return (y,mu);
  }
}.

import FMap.

import StdOrder.RealOrder.

op dA = dmatrix dRq k l.

op ds1 = dvector (dRq_ Params.eta_) l.

op ds2 = dvector (dRq_ Params.eta_) k.

op keygen : (PK * SK) distr =
  dlet (dmatrix dRq k l) (fun mA =>
  dlet ds1 (fun s1 =>
  dmap ds2 (fun s2 =>
  let pk = (mA, mA *^ s1 + s2) in
  let sk = (mA, s1, s2) in
  (pk, sk)))).

op dy = dvector (dRq_ (gamma1 - 1)) l.

op commit (sk : SK) : (commit_t * pstate_t) distr =
  let (mA, s1, s2) = sk in
  dmap dy (fun y =>
  let w1 = highBitsV (mA *^ y) in
  (w1, y)).

op respond (sk : SK) (c : challenge_t) (y: pstate_t) : response_t option =
  let (mA, s1, s2) = sk in
  let t0 = base2lowbitsV (mA *^ s1 + s2) in
  let w = mA *^ y in
  let z = y + c ** s1 in
  if inf_normv z < gamma1 - beta_ /\
     inf_normv (lowBitsV (mA *^ y - c ** s2) ) < gamma2 - beta_ then
    let h = makeHintV (- c ** t0) (w - c ** s2 + c ** t0) in
    Some (z, h)
    else None.

op verify (pk : PK) (w1 : commit_t) (c : challenge_t) (resp : response_t) : bool =
  let (mA, t) = pk in
  let t1 = base2highbitsV t in
  let (z, h) = resp in
  size z = l /\
  size h = k /\
  inf_normv z < gamma1 - beta_ /\
  w1 = useHintV h (mA *^ z - c ** base2shiftV t1).

lemma keygen_ll : is_lossless keygen.

proof.

apply dlet_ll => [|/= mA ?]; 1: by apply dmatrix_ll; apply dRq_ll.

apply dlet_ll => [|/= s1 ?]; 1: by apply dvector_ll; apply dRq__ll.

by apply dmap_ll; apply dvector_ll; apply dRq__ll.

qed.

lemma commit_ll sk : is_lossless (commit sk).

proof.

case: sk => mA s1 s2 @/commit /=.

by apply dmap_ll; apply dvector_ll; apply dRq__ll.

qed.

clone import FSaG.OpBased as OpBased with
  op keygen <= keygen,
  op commit <= commit,
  op response <= respond,
  op verify <= verify
proof keygen_ll by smt(keygen_ll commit_ll)
proof commit_ll by smt(keygen_ll commit_ll).

lemma size_t pk sk : (pk,sk) \in keygen => size pk.`2 = k.

proof.

case/supp_dlet => mA /= [s_mA].

case/supp_dlet => s1 /= [s_s1].

case/supp_dlet => s2 /= [s_s2].

rewrite /(\o) supp_dunit => -[-> _].

rewrite [Vectors.size]lock /= -lock.

rewrite size_addv size_mulmxv;
smt(size_dmatrix size_dvector gt0_k Params.gt0_l).

qed.

module OpBasedSig = FSaCR.IDS_Sig(OpBased.P, OpBased.V).

lemma pk_decomp mA' t' mA s1 s2 :
  ((mA', t'), (mA, s1, s2)) \in keygen =>
  mA' = mA /\ t' = mA *^ s1 + s2.

proof.

move => /supp_dlet H.

case H => x [? /supp_dlet H].

by case H => y [? /supp_dmap H] /#.

qed.

lemma sk_size mA s1 s2 :
  (exists pk, (pk, (mA, s1, s2)) \in keygen) => size mA = (k, l) /\ size s1 = l /\ size s2 = k.

proof.

move => [pk /supp_dlet valid_keys].

case valid_keys => [mA' [mA_supp /supp_dlet valid_keys]].

case valid_keys => [s1' [s1_supp /supp_dmap valid_keys]].

case valid_keys => [s2' [s2_supp [#]]] *; subst.

smt(size_dmatrix size_dvector gt0_k Params.gt0_l).

qed.

lemma keygen_supp_decomp pk mA s1 s2 :
  (pk, (mA, s1, s2)) \in keygen =>
  s1 \in ds1 /\
  s2 \in ds2.

proof.

move => /supp_dlet H.

case H => a [a_supp /supp_dlet H].

case H => v1 [v1_supp /supp_dmap H].

by case H => /= v2 [v2_supp [#]] *; subst.

qed.

hoare recover_correct (pk_i : PK) (sk_i : SK) :
  DID.Honest_Execution(OpBased.P, OpBased.V).get_trans :
  ((pk_i, sk_i) \in keygen /\ arg = (pk_i, sk_i)) ==>
  (res <> None => let (w, c, z) = oget res in w = recover pk_i c z).

proof.

case pk_i sk_i => [mA' t'] [mA s1 s2].

proc; inline *; auto => /> valid_keys.

have sk_sizes: size mA = (k, l) /\ size s1 = l /\ size s2 = k.

- by apply sk_size; exists (mA', t').

have rg_s2: s2 \in ds2 by smt(keygen_supp_decomp).

case /pk_decomp valid_keys => [??]; subst.

move => [w0 y0] @/commit /= /supp_dmap [y [y_supp [??]]] c c_supp H w c' z; subst.

have {H} H /=: (respond (mA, s1, s2) c y <> None) by smt().

rewrite H /respond /= => [#] *; subst c' w z.

rewrite ifT 1:/# /recover /=.

pose t := mA *^ s1 + s2.

pose t1 := base2highbitsV t.

pose t0 := base2lowbitsV t.

pose w := mA *^ y.

pose z := y + c ** s1.

rewrite mulmxvDr mulmx_scalarv -/w.

have W : w - c ** s2 = mA *^ z - c ** t0 - c ** base2shiftV t1.

rewrite /w /z mulmxvDr -!addvA; congr.

rewrite mulmx_scalarv -!scalarvN -2!scalarvDr.

congr.

rewrite -oppvD [t0+_]addvC b2high_lowPv /t.

by rewrite oppvD addvA addvN size_mulmxv /= lin_add0v /#.

have W' : w - c ** s2 + c ** t0 =  mA *^ z - c ** base2shiftV t1.

rewrite W -!addvA; congr; rewrite [_ + c**t0]addvC addvA [_ + c**t0]addvC addvN.

rewrite lin_add0v // size_oppv.

by rewrite !size_scalarv size_base2lowbitsV size_base2shiftV size_base2highbitsV.

rewrite W'.

have -> : w + c ** (mA *^ s1) = mA *^ z by rewrite /w /z mulmxvDr mulmx_scalarv.

rewrite usehint_correctV.

- rewrite size_addv !size_oppv !size_scalarv size_base2shiftV size_mulmxv.

have ->: size t0 = size t by smt(size_base2lowbitsV).

have ->: size t1 = size t by smt(size_base2highbitsV).

suff: size t = rows mA by smt().

by rewrite size_addv size_mulmxv /#.

- have ->: 2 * gamma2 %/ 2 = gamma2 by smt().

rewrite inf_normvN.

apply (StdOrder.IntOrder.ler_trans (tau * (2 ^ d %/ 2))).

apply l1_inf_norm_product_ub.

+ smt(tau_bound).

+ suff: 2 <= (2 ^ d) by smt().

apply StdOrder.IntOrder.ler_eexpr => //.

exact gt0_d.

+ smt(supp_dC).

+ suff: 2 ^ (d - 1) = 2 ^ d %/ 2 by smt(b2low_bound).

suff: 2 * 2 ^ (d - 1) = 2 ^ d by smt(Ring.IntID.expr_pred).

smt(Ring.IntID.exprS gt0_d).

+ smt(tau_bound ub_d gt0_d).

rewrite -addvA [(_ - _)%Vectors]addvC addvA -W.

have {1}-> : w = w - c**s2 + c**s2.

rewrite -addvA [_+ c**s2]addvC addvN size_scalarv.

rewrite addvC lin_add0v //; smt(size_mulmxv size_dvector).

have [C1 C2] {H} : inf_normv z < gamma1 - beta_ /\
                   inf_normv (lowBitsV (mA *^ y - c ** s2)) < gamma2 - beta_ by smt().

apply (hide_lowV _ _ beta_);
  1,2,3,5: smt(size_oppv size_scalarv size_mulmxv size_dvector size_addv
               gt0_beta beta_gamma2_lt).

apply: StdOrder.IntOrder.ler_trans eta_tau_leq_b; rewrite mulrC.

apply l1_inf_norm_product_ub; 1..3: smt(tau_bound gt0_eta supp_dC).

apply inf_normv_ler =>[|i rg_i]; first by smt(gt0_eta).

rewrite supp_dvector in rg_s2; first by smt(gt0_k).

by rewrite -supp_dRq; smt(gt0_eta).

qed.

op dsimz = dvector (dRq_open (gamma1 - beta_)) l.

op line12_magic_number = (size (to_seq (support dsimz)))%r / (size (to_seq (support dy)))%r.

op dsimoz : vector option distr =
   dlet (dbiased line12_magic_number)
        (fun b => if b then dmap dsimz Some else dunit None).

module HVZK_Sim_Inst : DID.HVZK_Sim = {
  proc get_trans(pk : PK) = {
    var mA, w', z, t,t0, resp,sample_z;
    var c <- witness;
    (mA, t) <- pk;
    t0 <- base2lowbitsV t;
    sample_z <$ dbiased line12_magic_number;
    if(sample_z) {
      c <$ FSa.dC;
      z <$ dsimz;
      w' <- mA *^ z - c ** t;
      resp <- if inf_normv (lowBitsV w') < gamma2 - beta_ then
        let h = makeHintV (- c ** t0) (w' + c ** t0) in Some (z, h)
      else None;
    } else {
      resp <- None;
    }
    return omap (fun z => (recover pk c z, c, z)) resp;
  }
}.

lemma mask_size :
  size (to_seq (support dsimz)) <= size (to_seq (support dy)).

proof.

apply leq_size_to_seq => [v|]; last exact is_finite_dy.

rewrite !supp_dRq_vect; smt(Params.gt0_l gt0_beta beta_gamma1_lt).

qed.

lemma mask_nonzero :
  0 < size (to_seq (support dsimz)).

proof.

suff: zerov l \in (to_seq (support dsimz)) by smt(size_eq0 List.size_ge0).

by rewrite mem_to_seq ?is_finite_dsimz dRq_zerov;
  smt(Params.gt0_l gt0_beta beta_gamma1_lt).

qed.

lemma clamp_magic : clamp line12_magic_number = line12_magic_number.

proof.

by rewrite clamp_id; smt(clamp_id mask_size mask_nonzero).

qed.

equiv HVZK_Sim_correct k :
  DID.Honest_Execution(OpBased.P, OpBased.V).get_trans ~ HVZK_Sim_Inst.get_trans :
  k \in keygen /\ arg{1} = k /\ arg{2} = k.`1 ==> ={res}.

proof.

case k => pk_i sk_i.

pose drop_commitment (wcz : commit_t * challenge_t * response_t) := (wcz.`2, wcz.`3).

conseq
  (_: (pk_i, sk_i) \in keygen /\ arg{1} = (pk_i, sk_i) /\ arg{2} = pk_i ==>
      omap drop_commitment res{1} = omap drop_commitment res{2})
  (_: arg = (pk_i, sk_i) /\ (pk, sk) \in keygen ==>
      res <> None => let (w, c, z) = oget res in w = (recover pk_i c z))
  (_: arg = pk_i ==>
      res <> None => let (w, c, z) = oget res in w = (recover pk_i c z)); 1, 2: smt().

- by conseq (recover_correct pk_i sk_i).

- proc; conseq (_ : _ ==> pk = pk_i); [ by auto => /> /# | by conseq /> ].

transitivity HVZK_Hops.game1
 ((pk_i, sk_i) \in keygen /\ arg{1} = (pk_i, sk_i) /\ arg{2} = (pk_i, sk_i) ==>
   omap drop_commitment res{1} = res{2})
 ((pk_i, sk_i) \in keygen /\ arg{1} = (pk_i, sk_i) /\ arg{2} = pk_i ==>
   res{1} = omap drop_commitment res{2}); 1, 2: smt().

- by proc; inline *; auto => /#.

transitivity HVZK_Hops.game9
  ((pk_i, sk_i) \in keygen /\ arg{1} = (pk_i, sk_i) /\ arg{2} = pk_i ==> ={res})
  ((pk_i, sk_i) \in keygen /\ arg{1} = pk_i /\ arg{2} = pk_i ==>
   res{1} = omap drop_commitment res{2}); 1, 2: smt().

- by conseq (KLS_HVZK pk_i sk_i).

proc.

sim : (={pk, c, resp}); smt().

qed.

lemma pr_HonestExecution_Sim &m p pk sk : (pk,sk) \in keygen =>
  Pr[DID.Honest_Execution(P, V).get_trans(pk, sk) @ &m : p res] =
  Pr[HVZK_Sim_Inst.get_trans(pk) @ &m : p res].

proof.

move => pk_sk; byequiv => //.

by conseq (HVZK_Sim_correct (pk,sk)) => />.

qed.

lemma pr_HonestExecution_op pk sk &m :
  (pk,sk) \in keygen =>
  Pr[DID.Honest_Execution(P, V).get_trans(pk,sk) @ &m : res = None] =
  mu (commit sk `*` dC tau)
     (fun (x : (ID.W * ID.Pstate) * ID.C) => respond sk x.`2 x.`1.`2 = None).

proof.

move => Hpk.

have -> : Pr[DID.Honest_Execution(P, V).get_trans(pk, sk) @ &m : res = None] =
          Pr[HVZK_Hops.game1(pk,sk) @ &m : res = None].

- byequiv (: ={arg} /\ arg{1} \in keygen ==> res{1} = None <=> res{2} = None) => //.

proc; inline*; auto => /> /#.

have <- : Pr[HE.sample(sk) @ &m : res = None] =
          mu (commit sk `*` dC tau)
             (fun (x : (ID.W * ID.Pstate) * ID.C) => respond sk x.`2 x.`1.`2 = None).

- byphoare (: arg = sk ==> _) => //; proc; rnd; skip => &hr />.

byequiv (_: arg.`2{1} = arg{2} ==> res{1} = None <=> res{2} = None) => //.

proc; wp.

conseq (: _ ==> ((w,st),c){1} = x{2}); 1: smt().

rnd (fun wsc : high list * pstate_t * challenge_t => ((wsc.`1,wsc.`2),wsc.`3))
    (fun wsc : (high list * pstate_t) * challenge_t => (wsc.`1.`1,wsc.`1.`2,wsc.`2)) : *0 *0.

skip => &1 &2; rewrite !andaE => *; do ! split.

- smt().

- case => -[] /= w1 y c ?.

rewrite dprod_dlet dmap_dlet /=.

rewrite !dlet1E; congr; apply/fun_ext => -[w1' y'] /=; congr; 1: smt().

rewrite !dmapE /(\o) /=.

by apply mu_eq => /> /#.

- case => w1 y c /=.

case/supp_dlet => -[w1' y'] [? /supp_dmap [c']] /> ?.

apply/supp_dmap; exists ((w1',y'),c'); smt(supp_dprod).

qed.

op ll_dflt (d : 'a distr) : 'a = choiceb (support d) witness.

lemma ll_dfltP (d : 'a distr) : is_lossless d => ll_dflt d \in d.

proof.

move => d_ll; apply: (choicebP (fun x => x \in d) witness) => /=.

move: d_ll.

rewrite /is_lossless weightE_support.

apply absurd => /= ?; rewrite mu0_false /#.

qed.

op check_mx : matrix -> bool.

axiom check_valid A : check_mx A => A \in dA.

const eps_comm  : { real | 0%r < eps_comm } as eps_comm_gt0.

op A0 : { matrix | check_mx A0 } as A0P.

axiom check_mx_entropy :
  E (dcond dA check_mx) (fun mA =>
    p_max (dmap dy (fun y => highBitsV (mA *^ y)))) <= eps_comm.

const eps_check : { real | 0%r <= eps_check }  as eps_check_gt0.

axiom check_mx_most : mu dA (predC check_mx) <= eps_check.

op dz = dvector (dRq_ (gamma1 - beta_ - 1)) l.

const eps_low : { real | eps_low < 1%r } as eps_low_lt1.

axiom bound_low c (t : vector) (mA : matrix) :
  c \in dC tau => t \in dvector dRq k => check_mx mA =>
  mu dz (fun z => gamma2 - beta_ <= inf_normv (lowBitsV (mA *^ z - c ** t)) ) <= eps_low.

op p_rej = line12_magic_number * eps_low + (1%r - line12_magic_number).

lemma gt0_magic_number : 0%r < line12_magic_number.

proof.

suff: 0 < size (to_seq (support dsimz)) /\ 0 < size (to_seq (support dy)) by smt().

rewrite !gt0_dRq_vect; smt(Params.gt0_l gt0_beta beta_gamma1_lt).

qed.

lemma p_rej_bounded : 0%r <= p_rej < 1%r.

have ? : 0%r < line12_magic_number <= 1%r.

- rewrite gt0_magic_number /= /line12_magic_number.

suff: 0 < size (to_seq (support dy)) by smt(mask_size size_ge0).

apply gt0_dRq_vect; smt(Params.gt0_l beta_gamma1_lt gt0_beta).

suff: 0%r <= eps_low < 1%r by smt().

rewrite eps_low_lt1 /=.

pose c0 := ll_dflt (dC tau).

pose t0 := ll_dflt (dvector dRq k).

suff: mu dz (fun z => gamma2 - beta_ <= inf_normv (lowBitsV (A0 *^ z - c0 ** t0))) <= eps_low.

- smt(ge0_mu).

apply bound_low.

- by rewrite ll_dfltP dC_ll.

- by rewrite ll_dfltP dvector_ll dRq_ll.

- exact A0P.

qed.

op check (sk : SK) : bool = check_mx (sk.`1) /\ sk.`2 \in ds1 /\ sk.`3 \in ds2.

import StdBigop.Bigreal.BRA.

import StdOrder.RealOrder.

lemma dmap_keygen : dmap keygen (fun (k : PK * SK) => k.`2.`1) = dA.

proof.

have ds1_ll : is_lossless ds1 by apply/dvector_ll/dRq__ll.

have ds2_ll : is_lossless ds2 by apply/dvector_ll/dRq__ll.

apply eq_distr => mA.

rewrite dmap1E.

rewrite /keygen -/dA -dmapE dmap_dlet /= dletEunit // => {mA} mA.

rewrite dmap_dlet; apply dletEconst => //= s1.

by rewrite dmap_comp /dmap; apply dletEconst.

qed.

lemma check_entropy: E (dcond keygen (fun k : (PK * SK) => check k.`2))
                          (fun (k : PK * SK) =>
                             p_max (dfst ((commit k.`2)))) <= eps_comm.

proof.

apply: StdOrder.RealOrder.ler_trans check_mx_entropy.

pose g (mA : matrix) := p_max (dmap dy (fun (y : vector) => highBitsV (mA *^ y))).

pose f (k : PK * SK) := k.`2.`1.

have -> : (fun (k : PK * SK) => p_max (dfst ((commit k.`2)))) = g \o f.

apply/fun_ext => -[pk [A s1 s2]] @/(\o) @/f @/g @/commit /=.

by rewrite dmap_comp.

rewrite -exp_dmap.

- pose d := dmap _ _; rewrite /hasE.

rewrite (eq_summable _ (fun x => mu1 d x * g x)) 1:/#.

apply/summable_mu1_wght; smt(ge0_pmax le1_pmax).

apply lerr_eq; congr; apply/eq_distr => mA.

rewrite (eq_dcond _ _ (check_mx \o f)); 1: smt(keygen_supp_decomp).

by rewrite dmap_dcond dmap_keygen.

qed.

lemma check_most : mu keygen (fun k : PK * SK => !check k.`2) <= eps_check.

proof.

apply: StdOrder.RealOrder.ler_trans check_mx_most.

rewrite (mu_eq_support _ _ ((predC check_mx) \o (fun k : PK*SK => k.`2.`1))).

smt(keygen_supp_decomp).

by rewrite -dmapE (mu_eq_l dA) // dmap_keygen.

qed.

lemma get_pk (sk : SK) : check sk => exists pk, (pk,sk) \in keygen.

proof.

case: sk => mA s1 s2 [|> chk_mA s1_d s2_d]; exists (mA,mA *^ s1 + s2).

rewrite supp_dlet; exists mA; rewrite check_valid //=.

rewrite supp_dlet; exists s1; rewrite s1_d //=.

by rewrite supp_dmap; exists s2; rewrite s2_d.

qed.

lemma rej_bound (sk : SK) :
  check sk =>
  mu (commit sk `*` dC tau)
     (fun (x : (ID.W * ID.Pstate) * ID.C) => respond sk x.`2 x.`1.`2 = None) <= p_rej.

proof.

move => chk_sk; have [pk pk_sk] := get_pk _ chk_sk.

have [&m _] : exists &m, true by smt().

have /= <- := pr_HonestExecution_op pk sk &m pk_sk.

have -> := pr_HonestExecution_Sim &m (pred1 None) pk sk pk_sk.

have [A' t' [def_pk chk_A]] : exists A t, pk = (A,t) /\ check_mx A; 2: subst.

case: pk pk_sk => A t pk_sk; exists A t => /=.

smt(pk_decomp).

byphoare (: arg = (A',t') ==> _) => //; proc.

conseq (: _ ==> resp = None); 1: smt().

seq 4 : (sample_z) line12_magic_number eps_low (1%r - line12_magic_number) 1%r
        (mA = A' /\ t = t').

- by auto.

- rnd.

auto => _ _.

by rewrite dbiasedE /= clamp_magic.

- rcondt ^if; 1: by auto.

wp; conseq (: _ ==> gamma2 - beta_ <= inf_normv (lowBitsV (mA *^ z - c ** t))); 1: smt().

rnd.

auto => /> &1 _ c c_dC.

apply bound_low => //.

rewrite supp_dvector ?ltzW ?gt0_k; move/size_t : pk_sk; smt(dRq_fu).

- rnd; auto => _ _.

by rewrite dbiasedE /= clamp_magic.

- by auto.

- done.

qed.

lemma keygen_finite : is_finite (support keygen).

proof.

apply finite_dlet => [|mA ? /=]; first exact/uniform_finite/dmatrix_uni/dRq_uni.

apply finite_dlet => [|s1 ? /=]; first exact/uniform_finite/dvector_uni/dRq__uni.

apply finite_dlet; first exact/uniform_finite/dvector_uni/dRq__uni.

by move => s2 ? @/(\o); exact finite_dunit.

qed.

import FSaCR.DSS.

import FSaCR.DSS.PRO.

import FSaCR.DSS.DS.Stateless.

import FSaCR.DSS.EFCMA.

module type SigDist (S : Scheme) (H : Hash_i) = {
  proc distinguish() : bool
}.

module OpBasedSigG     = FSaG.IDS_Sig(OpBased.P,OpBased.V).

module O_CMA_Default_G = FSaG.DSS.DS.Stateless.O_CMA_Default.

module RO_G            = FSaG.DSS.PRO.RO.

module EF_CMA_RO_G = FSaG.DSS.EF_CMA_RO.

module EF_KOA_RO_G = FSaG.DSS.EF_KOA_RO.

clone FSaCR.CRtoGen as CG.

clone import OpBased.CMAtoKOA as CMAtoKOA with
  op p_rej <- p_rej,
  op check_entropy <- check,
  op eps <- eps_comm,
  op dlt <- eps_check
proof *.

realize eps_gt0 by apply eps_comm_gt0.

realize check_entropy_correct by apply check_entropy.

realize most_keys_high_entropy by apply check_most.

realize p_rej_bounded by smt(p_rej_bounded).

realize rej_bound by apply rej_bound.

realize keygen_finite by apply keygen_finite.

module (RedCR (A : Self.FSaG.DSS.Adv_EFKOA_RO) : Adv_EFKOA_RO) (H : Hash) = {
  proc forge (pk : PK) : M*Sig = {
    var m,sig,w,z,c;
    (m,sig) <@ A(H).forge(pk);
    (w,z) <- sig;
    c <@ H.get(w,m);
    return (m,(c,z));
  }
}.

module RedNMA(A : Adv_EFCMA_RO) = RedCR(RedKOA(CG.RedFSaG(A),HVZK_Sim_Inst)).

require import FMap.

module CountS (O : SOracle_CMA) = {
  var qs : int
  proc init() = { qs <- 0; }

  proc sign (m : M) = {
    var s;
    qs <- qs + 1;
    s <@ O.sign(m);
    return s;
  }
}.

module CountH (H : Hash) = {
  var qh : int
  proc init() = { qh <- 0; }

  proc get (w,m) = {
    var c;
    qh <- qh + 1;
    c <@ H.get(w,m);
    return c;
  }
}.

import Self.FSaG.

import Self.FSaG.DSS.

import Self.FSaG.DSS.PRO.

import Self.FSaG.DSS.DS.Stateless.
