require import AllCore Distr List FMap Dexcepted PKE_ROM StdOrder.

require   MLWE FLPRG.

theory MLWE_PKE_Hash.

clone import MLWE as MLWE_.

import Matrix_.

import ZR.

import StdOrder.IntOrder Matrix_ Big.BAdd.

type plaintext.

type ciphertext.

type raw_ciphertext = vector * R.

op m_encode : plaintext -> R.

op m_decode : R -> plaintext.

op c_encode : raw_ciphertext -> ciphertext.

op c_decode : ciphertext -> raw_ciphertext.

type pkey.

type skey.

type raw_pkey  = seed * vector.

type raw_skey  = vector.

op pk_encode : raw_pkey -> pkey.

op sk_encode : raw_skey -> skey.

op pk_decode : pkey -> raw_pkey.

op sk_decode : skey -> raw_skey.

axiom pk_encodeK : cancel pk_encode pk_decode.

axiom sk_encodeK : cancel sk_encode sk_decode.

type randomness.

op [uniform full lossless]drand : randomness distr.

op prg_kg : randomness -> seed * vector * vector.

op prg_kg_ideal  =
     dlet dseed
       (fun (sd : seed) =>
          dlet dshort (fun (s : vector) =>
               dmap dshort (fun (e : vector) => (sd, s, e)))).

op prg_enc : randomness -> vector * vector * R.

op prg_enc_ideal =
     dlet dshort
       (fun (r : vector) =>
          dlet dshort (fun (e1 : vector) =>
               dmap dshort_R (fun (e2 : R) => (r, e1, e2)))).

op kg(r : randomness) : pkey * skey =
   let (sd,s,e) = prg_kg r in
   let t =  (H sd) *^ s + e in
       (pk_encode (sd,t),sk_encode s).

op enc(rr : randomness, pk : pkey, m : plaintext) : ciphertext =
    let (sd,t) = pk_decode pk in
    let (r,e1,e2) = prg_enc rr in
    let u = m_transpose (H sd) *^ r + e1 in
    let v = (t `<*>` r) &+ e2 &+ (m_encode m) in
        c_encode (u,v).

op dec(sk : skey, c : ciphertext) : plaintext option =
    let (u,v) = c_decode c in
       Some (m_decode (v &- (sk_decode sk `<*>` u))).

require FO_MLKEM.

clone import FO_MLKEM with
  type UU.TT.PKE.pkey <- MLWE_PKE_Hash.pkey,
  type UU.TT.PKE.skey <- MLWE_PKE_Hash.skey,
  type UU.TT.PKE.ciphertext <- MLWE_PKE_Hash.ciphertext,
  type UU.TT.plaintext <- MLWE_PKE_Hash.plaintext,
  type UU.TT.randomness <- MLWE_PKE_Hash.randomness,
  op UU.TT.kg = dmap drand kg,
  op UU.TT.enc <- enc,
  op UU.TT.dec <- dec,
  op UU.TT.randd <- drand
  proof UU.TT.kg_ll by (apply dmap_ll;apply drand_ll)
  proof UU.TT.randd_ll by apply drand_ll.

import UU.TT.PKE.

module MLWE_PKE_HASH : Scheme = {

  proc kg() : pkey * skey = {
     var r,pk,sk;
     r <$ drand;
     (pk,sk) <- kg r;
     return (pk,sk);
  }

  proc enc(pk : pkey, m : plaintext) : ciphertext = {
     var rr,c;
     rr <$ drand;
     c <- enc rr pk m;
     return c;
  }

  proc dec(sk : skey, c : ciphertext) : plaintext option = {
    var mo;
    mo <- dec sk c;
    return mo;
  }
}.

module MLWE_PKE_HASH_PROC : Scheme = {

  proc kg_bridge() : pkey * skey = {
     var r,sd,s,e,t;
     r <$ drand;
     (sd,s,e) <- prg_kg r;
     t <-  (H sd) *^ s + e;
     return (pk_encode (sd,t),sk_encode s);
  }

  proc kg() : pkey * skey = {
    var sd,s,e,t;
    sd <$ dseed;
    s  <$ dshort;
    e  <$ dshort;
    t  <- (H sd) *^ s + e;
    return (pk_encode (sd,t),sk_encode s);
  }

  proc enc_bridge(pk : pkey, m : plaintext) : ciphertext = {
     var sd,t,rr,r,e1,e2,u,v;
     (sd,t) <- pk_decode pk;
     rr <$ drand;
     (r,e1,e2) <- prg_enc rr;
     u <- m_transpose (H sd) *^ r + e1;
     v <- (t `<*>` r) &+ e2 &+ (m_encode m);
     return c_encode (u,v);
  }

  proc enc(pk : pkey, m : plaintext) : ciphertext = {
    var sd, t,r,e1,e2,u,v;
    (sd,t) <- pk_decode pk;
    r  <$ dshort;
    e1 <$ dshort;
    e2 <$ dshort_R;
    u  <- m_transpose (H sd) *^ r + e1;
    v  <- (t `<*>` r) &+ e2 &+ (m_encode m);
    return c_encode (u,v);
  }

  proc dec(sk : skey, c : ciphertext) : plaintext option = {
    var u,v;
    (u,v) <- c_decode c;
    return (Some (m_decode (v &- (sk_decode sk `<*>` u))));
  }
}.

clone import FLPRG as PRG_KG with
  type seed <- randomness,
  type output <- seed * vector * vector,
  op prg <- prg_kg,
  op dseed <- drand,
  op dout <- prg_kg_ideal
  proof *.

clone import FLPRG as PRG_ENC with
  type seed <- randomness,
  type output <- vector * vector * R,
  op prg <- prg_enc,
  op dseed <- drand,
  op dout <- prg_enc_ideal
  proof*.

module MLWE_PKE_HASH_PRG : Scheme  = {
  var sd : seed
  var s  : vector
  var e  : vector
  var r  : vector
  var e1 : vector
  var e2 : R

  proc kg() : pkey * skey = {
     var t;
     t <-  (H sd) *^ s + e;
     return (pk_encode (sd,t),sk_encode s);
  }

  proc enc(pk : pkey, m : plaintext) : ciphertext = {
     var sd,t,u,v;
     (sd,t) <- pk_decode pk;
     u <- m_transpose (H sd) *^ r + e1;
     v <- (t `<*>` r) &+ e2 &+ (m_encode m);
     return c_encode (u,v);
  }

  include MLWE_PKE_HASH [dec]
}.

module (D_KG(A : Adversary) : PRG_KG.Distinguisher)  = {
   proc distinguish(sd : seed, s : vector, e : vector) : bool = {
       var coins,b;
       MLWE_PKE_HASH_PRG.sd <- sd;
       MLWE_PKE_HASH_PRG.s <- s;
       MLWE_PKE_HASH_PRG.e <- e;
       coins <$ drand;
       (MLWE_PKE_HASH_PRG.r,MLWE_PKE_HASH_PRG.e1,MLWE_PKE_HASH_PRG.e2) <- prg_enc coins;
       b <@ CPA(MLWE_PKE_HASH_PRG,A).main();
       return b;
   }
}.

module (D_ENC(A : Adversary) : PRG_ENC.Distinguisher) = {
   proc distinguish(r : vector, e1 : vector, e2 : R) : bool = {
       var b;
       (MLWE_PKE_HASH_PRG.sd,MLWE_PKE_HASH_PRG.s,MLWE_PKE_HASH_PRG.e) <$ prg_kg_ideal;
       MLWE_PKE_HASH_PRG.r <- r;
       MLWE_PKE_HASH_PRG.e1 <- e1;
       MLWE_PKE_HASH_PRG.e2 <- e2;
       b <@ CPA(MLWE_PKE_HASH_PRG,A).main();
       return b;
   }
}.

module (DC_KG(A : CORR_ADV) : PRG_KG.Distinguisher)  = {
   proc distinguish(sd : seed, s : vector, e : vector) : bool = {
       var coins,b;
       MLWE_PKE_HASH_PRG.sd <- sd;
       MLWE_PKE_HASH_PRG.s <- s;
       MLWE_PKE_HASH_PRG.e <- e;
       coins <$ drand;
       (MLWE_PKE_HASH_PRG.r,MLWE_PKE_HASH_PRG.e1,MLWE_PKE_HASH_PRG.e2) <- prg_enc coins;
       b <@ Correctness_Adv(MLWE_PKE_HASH_PRG,A).main();
       return b;
   }
}.

module (DC_ENC(A : CORR_ADV) : PRG_ENC.Distinguisher) = {
   proc distinguish(r : vector, e1 : vector, e2 : R) : bool = {
       var b;
       (MLWE_PKE_HASH_PRG.sd,MLWE_PKE_HASH_PRG.s,MLWE_PKE_HASH_PRG.e) <$ prg_kg_ideal;
       MLWE_PKE_HASH_PRG.r <- r;
       MLWE_PKE_HASH_PRG.e1 <- e1;
       MLWE_PKE_HASH_PRG.e2 <- e2;
       b <@ Correctness_Adv(MLWE_PKE_HASH_PRG,A).main();
       return b;
   }
}.

module MLWE_PKE_HASH1 = {
  proc kg() : pkey * skey = {
    var sd,s,t;
    sd <$ dseed;
    s  <$ dshort;
    t  <$ duni;
    return (pk_encode (sd,t), sk_encode s);
  }

  include MLWE_PKE_HASH_PROC [-kg]

}.

module B1(A : Adversary) : HAdv_T = {

  proc kg(sd : seed, t : vector) : pkey * skey = {
    return (pk_encode (sd,t),witness);
  }

  proc guess(sd, t : vector, uv : vector * R) : bool = {
    var pk, sk, m0, m1, c, b, b';
    (pk,sk) <@ kg(sd,uv.`1);
    (m0, m1) <@ A.choose(pk);
    b <$ {0,1};
    c <@ MLWE_PKE_HASH1.enc(pk, if b then m1 else m0);
    b' <@ A.guess(c);
    return b' = b;
  }
}.

module MLWE_PKE_HASH2 = {

  proc enc(pk : pkey, m : plaintext) : ciphertext = {
    var _A,u, v;
    _A <- m_transpose (H (pk_decode pk).`1);
    u <$duni;
    v <$duni_R;
    return c_encode (u,v &+ m_encode m);
  }

  include MLWE_PKE_HASH1 [-enc]

}.

module B2(A : Adversary) : HAdv_T = {

  proc kg(sd : seed, t : vector) : pkey * skey = {
    return (pk_encode (sd,t),witness);
  }

  proc enc(pk : pkey, m : plaintext, uv : vector * R) : ciphertext = {
    return c_encode ((uv.`1, uv.`2 &+ m_encode m));
  }

  proc guess(sd : seed, t : vector, uv : vector * R) : bool = {
    var pk, sk, m0, m1, c, b, b';
    (pk,sk) <@ kg(sd,t);
    (m0, m1) <@ A.choose(pk);
    b <$ {0,1};
    c <@ enc(pk, if b then m1 else m0,uv);
    b' <@ A.guess(c);
    return b' = b;
  }

}.

op noise_exp _A s e r e1 e2 m =
    let t = _A *^ s + e in
    let u = m_transpose _A *^ r + e1 in
    let v = (t `<*>` r) &+ e2 &+ (m_encode m) in
    let (u',v') = c_decode (c_encode (u,v)) in
        v' &- (s `<*>` u') &- (m_encode m).

op rnd_err_v : R -> R.

op rnd_err_u : vector -> vector.

axiom encode_noise u v :
   c_decode (c_encode (u,v)) =
      (u + rnd_err_u u, v &+ rnd_err_v v).

op max_noise : int.

op under_noise_bound : R -> int -> bool.

axiom good_decode m n :
  under_noise_bound n max_noise =>
  m_decode (m_encode m &+ n) = m.

module CorrectnessAdvNoise(A : CORR_ADV) = {
  proc main() = {
    var sd,s,e,_A,r,e1,e2,m,n;
    sd <$ dseed;
    _A <- H sd;
    r <$ dshort;
    s <$ dshort;
    e <$ dshort;
    e1 <$ dshort;
    e2 <$ dshort_R;
    m <@ A.find(pk_encode (sd,_A *^ s + e),sk_encode s);
    n <- noise_exp _A s e r e1 e2 m;
    return (!under_noise_bound n max_noise);
  }
}.

axiom noise_commutes n n' maxn (b : int) :
  under_noise_bound n' b =>
  under_noise_bound n (maxn - b) =>
  under_noise_bound (n &+ n') maxn.

axiom noise_preserved n maxn :
  under_noise_bound n maxn =
  under_noise_bound (ZR.([-]) n) maxn.

op noise_exp_part1 _A s e r e1 e2 =
  let u = m_transpose _A *^ r + e1 in
  let cu = rnd_err_u u in
    ((e `<*>` r) &- (s `<*>` e1) &+ e2 ) &-   (s `<*>` cu).

op noise_exp_part2 _A s e r e2 m =
  let t = _A *^ s + e in
  let v = (t `<*>` r) &+ e2 &+ (m_encode m) in
  let cv = rnd_err_v v in
  cv.

module CB(A : CORR_ADV) = {
  var s : vector
  var e : vector
  var _A : matrix
  var r : vector
  var e1 : vector
  var e2 : R
  var n1 : R
  var n2 : R
  var u : vector
  var cu : vector
  var m : plaintext


  proc main() = {
    var sd;
    sd <$ dseed;
    _A <- H sd;
    r <$ dshort;
    s <$ dshort;
    e <$ dshort;
    e1 <$ dshort;
    e2 <$ dshort_R;
    m <@ A.find(pk_encode (sd,_A *^ s + e),sk_encode s);
    n1 <- noise_exp_part1 _A s e r e1 e2;
    n2 <- noise_exp_part2 _A s e r e2 m;
  }
}.

op cv_bound_max : int.

axiom cv_bound_valid _A s e r e2 m :
  s \in dshort =>
  e \in dshort =>
  r \in dshort =>
  e2 \in dshort_R =>
  let t = _A *^ s + e in
  let v = (t `<*>` r) &+ e2 &+ (m_encode m) in
  under_noise_bound (rnd_err_v v) cv_bound_max.

module CorrectnessBound = {

  proc main() = {
    var sd, _A, r,s,e,e1,e2,n;
    sd <$ dseed;
    _A <- H sd;
    r <$ dshort;
    s <$ dshort;
    e <$ dshort;
    e1 <$ dshort;
    e2 <$ dshort_R;
    n <- noise_exp_part1 _A s e r e1 e2;
    return !under_noise_bound n (max_noise - cv_bound_max);
  }
}.

import UU.TT.PKEROM.

import UU.

section.

declare module A <:
    KEMROM.CCA_ADV{ -KEMROM.RO.RO.m, -OW_CPA, -BOWp, -OWL_CPA, -OWvsIND.Bowl, -RO.RO, -RO.FRO, -OW_PCVA, -TT.BasePKE, -TT.B, -TT.Correctness_Adv1, -TT.CountO, -TT.O_AdvOW, -TT.Gm, -RF.RF, -PseudoRF.PRF, -KEMROMx2.RO1.RO, -KEMROMx2.RO1.FRO, -KEMROMx2.RO2.RO, -KEMROMx2.RO2.FRO, -KEMROMx2.CCA, -CountHx2, -RO1E.FunRO, -UU2, -H2, -H2BOWMod, -Gm2, -Gm3, -KEMROM.CCA, -B1x2, -CB, -MLWE_PKE_HASH_PRG}.


  (* SCRATCHPAD BEGIN — your own declarations may go below this line *)
lemma mlkem_noise_split aa ss ee rr ee1 ee2 mm :
  noise_exp aa ss ee rr ee1 ee2 mm =
    noise_exp_part1 aa ss ee rr ee1 ee2 &+
    noise_exp_part2 aa ss ee rr ee2 mm.
proof.
  rewrite /noise_exp /noise_exp_part1 /noise_exp_part2 /= encode_noise /=.
  rewrite !dotpDl !dotpDr dotp_mulmxv -mulmxTv.
  ring.
qed.

lemma mlkem_short_ll : is_lossless dshort.
proof. exact (dvector_ll dshort_R dshort_R_ll). qed.

lemma mlkem_uni_ll : is_lossless duni.
proof. exact (dvector_ll duni_R duni_R_ll). qed.

lemma mlkem_decode_good aa ss ee rr ee1 ee2 mm :
  ss \in dshort => ee \in dshort => rr \in dshort => ee2 \in dshort_R =>
  under_noise_bound (noise_exp_part1 aa ss ee rr ee1 ee2)
    (max_noise - cv_bound_max) =>
  dec (sk_encode ss)
    (c_encode (m_transpose aa *^ rr + ee1,
      ((aa *^ ss + ee) `<*>` rr) &+ ee2 &+ m_encode mm)) = Some mm.
proof.
  move=> hs he hr he2 hn.
  have hcv := cv_bound_valid aa ss ee rr ee2 mm hs he hr he2.
  have hn' : under_noise_bound (noise_exp aa ss ee rr ee1 ee2 mm) max_noise.
  + rewrite mlkem_noise_split; apply (noise_commutes _ _ _ cv_bound_max) => //.
  rewrite /dec sk_encodeK /=.
  have hg := good_decode mm (noise_exp aa ss ee rr ee1 ee2 mm) hn'.
  rewrite /noise_exp /= encode_noise /= in hg.
  rewrite encode_noise /=.
  have heq : forall (vv : R), m_encode mm &+ (vv &- m_encode mm) = vv.
  + by move=> vv; rewrite ZR.addrC ZR.subrK.
  by move: hg; rewrite heq.
qed.
section MlkemCorrectness.
declare module QC <: TT.PKE.CORR_ADV{-MLWE_PKE_HASH_PRG, -CB}.

lemma mlkem_ideal_correctness &m :
  islossless QC.find =>
  Pr[TT.PKE.Correctness_Adv(MLWE_PKE_HASH_PROC, QC).main() @ &m : res] <=
  Pr[CorrectnessBound.main() @ &m : res].
proof.
(* COMPLETE THIS *)
  move=> qll.
  byequiv (_ : true ==> res{1} => res{2}) => //.
  proc; inline *.
  swap{2} 3 2.
  swap{1} 10 -4; swap{1} 11 -4; swap{1} 12 -4.
  wp; call{1} qll; wp.
  rnd; rnd; rnd; wp; rnd; rnd; wp; rnd; skip.
  progress.
  apply negP => hn.
  have hd := mlkem_decode_good (MLWE_.H sdL) sL eL rL e1L e2L result H1 H3 H5 H9 hn; move: H11; rewrite pk_encodeK /=; move: hd; rewrite /dec /=; smt().
qed.
end section MlkemCorrectness.

section MlkemCPA.
declare module QP <: TT.PKE.Adversary{-MLWE_PKE_HASH_PRG}.

lemma mlkem_cpa_mlwe_first &m :
  Pr[TT.PKE.CPA(MLWE_PKE_HASH_PROC, QP).main() @ &m : res] =
  Pr[MLWE_H(B1(QP)).main(false, false) @ &m : res].
proof.
  byequiv (_ : ={glob QP} /\ !tr{2} /\ !b{2} ==> ={res}) => //.
  proc; inline *.
  wp; call (_ : true); wp.
  rnd; rnd; rnd; wp; rnd; call (_ : true); wp.
  rnd{2}; wp; rnd{2}; rnd{2}; rnd{2}; wp.
  rnd; rnd; rnd; auto.
  smt(mlkem_uni_ll duni_R_ll dshort_R_ll).
qed.
lemma mlkem_cpa_mlwe_first_random &m :
  Pr[TT.PKE.CPA(MLWE_PKE_HASH1, QP).main() @ &m : res] =
  Pr[MLWE_H(B1(QP)).main(false, true) @ &m : res].
proof.
  byequiv (_ : ={glob QP} /\ !tr{2} /\ b{2} ==> ={res}) => //.
  proc; inline *.
  wp; call (_ : true); wp.
  rnd; rnd; rnd; wp; rnd; call (_ : true); wp.
  rnd{2}; wp; rnd{2}; rnd{2}; rnd; wp; rnd{2}; rnd; rnd; auto.
  smt(mlkem_uni_ll duni_R_ll dshort_R_ll mlkem_short_ll).
qed.

lemma mlkem_cpa_mlwe_second &m :
  Pr[TT.PKE.CPA(MLWE_PKE_HASH1, QP).main() @ &m : res] =
  Pr[MLWE_H(B2(QP)).main(true, false) @ &m : res].
proof.
  byequiv (_ : ={glob QP} /\ tr{2} /\ !b{2} ==> ={res}) => //.
  proc; inline *.
  swap{1} 10 -8; swap{1} 11 -8; swap{1} 12 -6.
  wp; call (_ : true); wp; rnd; call (_ : true); wp.
  rnd{2}; wp; rnd; rnd; rnd{1}; rnd{2}; wp; rnd; rnd; rnd; auto.
  smt(mlkem_uni_ll duni_R_ll mlkem_short_ll pk_encodeK).
qed.

lemma mlkem_cpa_mlwe_second_random &m :
  Pr[TT.PKE.CPA(MLWE_PKE_HASH2, QP).main() @ &m : res] =
  Pr[MLWE_H(B2(QP)).main(true, true) @ &m : res].
proof.
  byequiv (_ : ={glob QP} /\ tr{2} /\ b{2} ==> ={res}) => //.
  proc; inline *.
  swap{1} 10 -7; swap{1} 11 -6.
  wp; call (_ : true); wp; rnd; call (_ : true); wp.
  rnd; wp; rnd{2}; rnd; rnd; wp; rnd{2}; rnd; rnd; auto.
  smt(dshort_R_ll mlkem_short_ll).
qed.

module MlkemFlat = {
  proc enc(pk : pkey, m : plaintext) : ciphertext = {
    var u, v;
    u <$ duni;
    v <$ duni_R;
    return c_encode (u,v);
  }
  include MLWE_PKE_HASH2 [-enc]
}.

lemma mlkem_uniform_pad &m :
  Pr[TT.PKE.CPA(MLWE_PKE_HASH2, QP).main() @ &m : res] =
  Pr[TT.PKE.CPA(MlkemFlat, QP).main() @ &m : res].
proof.
  byequiv (_ : ={glob QP} ==> ={res}) => //.
  proc; inline *.
  wp; call (_ : true); wp.
  rnd (fun vv => vv &+ m_encode m{1}) (fun vv => vv &- m_encode m{1}).
  rnd; wp; rnd; call (_ : true); auto.
  progress; ring.
qed.

lemma mlkem_uniform_half &m :
  islossless QP.choose => islossless QP.guess =>
  Pr[TT.PKE.CPA(MlkemFlat, QP).main() @ &m : res] = 1%r/2%r.
proof.
  move=> qcll qgll.
  byphoare (_ : true ==> res) => //.
  proc; inline *.
  kill 7 ! 2; first by auto.
  swap 6 4.
  seq 9 : true 1%r (1%r/2%r) 0%r 0%r => //.
  + by islossless; smt(mlkem_short_ll mlkem_uni_ll).
  + rnd (pred1 b'); skip; progress; smt(DBool.dbool1E).
qed.
lemma mlkem_cpa_prg_real &m :
  Pr[TT.PKE.CPA(MLWE_PKE_HASH, QP).main() @ &m : res] =
  Pr[PRG_KG.IND(PRG_KG.PRGr, D_KG(QP)).main() @ &m : res].
proof.
  byequiv (_ : ={glob QP} ==> ={res}) => //.
  proc; inline *.
  swap{1} 8 -4.
  wp; call (_ : true); wp; rnd; call (_ : true); wp.
  rnd; wp; rnd; auto.
  rewrite /kg /enc /=; smt().
qed.

op mlkem_split_map (pp : pkey)
  (whole auxiliary : (plaintext * pkhash, key * randomness) fmap)
  (coins : (plaintext, randomness) fmap) (keys : (plaintext, key) fmap) =
  (forall mm, coins.[mm] = None <=> keys.[mm] = None) /\
  forall mm hh, whole.[(mm,hh)] =
    if hh = pkh pp then omap (fun rr => (oget keys.[mm], rr)) coins.[mm]
    else auxiliary.[(mm,hh)].

module MlkemNoDec = {
  proc dec(c : ciphertext) : key option = { return None; }
}.

lemma mlkem_split_get (QD <: KEMROMx2.CCA_ORC) :
  equiv [KEMROM.RO.RO.get ~
  B1x2(A, KEMROMx2.RO_x2(KEMROMx2.RO1.RO, KEMROMx2.RO2.RO), QD).BH.get :
  ={arg} /\
  mlkem_split_map B1x2._pk{2} KEMROM.RO.RO.m{1} KEMROM.RO.RO.m{2}
    KEMROMx2.RO1.RO.m{2} KEMROMx2.RO2.RO.m{2}
  ==>
  ={res} /\
  mlkem_split_map B1x2._pk{2} KEMROM.RO.RO.m{1} KEMROM.RO.RO.m{2}
    KEMROMx2.RO1.RO.m{2} KEMROMx2.RO2.RO.m{2}].
proof.
(* COMPLETE THIS *)
  proc; inline *.
  case (hpk{2} = pkh B1x2._pk{2}).
  rcondt{2} 5; first by auto.
  swap{2} 10 -9; swap{2} 7 -5.
  seq 1 2 : ((x{1} = (m{2}, hpk{2}) /\ mlkem_split_map B1x2._pk{2} KEMROM.RO.RO.m{1} KEMROM.RO.RO.m{2} KEMROMx2.RO1.RO.m{2} KEMROMx2.RO2.RO.m{2}) /\ hpk{2} = pkh B1x2._pk{2} /\ r{1} = (r2{2}, r1{2})).
  rndsem*{2} 0; auto => *.
  rewrite !dprod_dlet /dmap /=.
  rewrite /(\o) /=.
  by move=> [a b] /= H; rewrite H /=; assumption.
  wp; rnd{2}; wp; skip.
  move=> &1 &2 [[Hx [Hdom Hmap]] [Hpk Hr]] r0 Hr0; rewrite -/mlkem_split_map in Hmap.
  move=> Hsupp; rewrite /r0 Hx Hr !domE Hmap Hpk /=; case (KEMROMx2.RO1.RO.m{2}.[m{2}] = None) => Hcoins.
  rewrite -(Hdom m{2}) Hcoins /= !get_set_sameE /=; case (KEMROM.RO.RO.m{2}.[m{2}, pkh B1x2._pk{2}] = None) => Haux; rewrite /mlkem_split_map /=; split.
  move=> mm; rewrite !get_setE; case (mm = m{2}) => H /=.
  trivial.
  by apply Hdom.
  by move=> mm hh; rewrite !get_setE Hmap /=; case (hh = pkh B1x2._pk{2}) => Hh; case (mm = m{2}) => Hm; rewrite /=.
  by move=> mm; rewrite !get_setE; case (mm = m{2}) => H //=; apply Hdom.
  by move=> mm hh; rewrite !get_setE Hmap /=; case (hh = pkh B1x2._pk{2}) => Hh; case (mm = m{2}) => Hm; rewrite /=.
  rewrite -(Hdom m{2}) Hcoins /= (some_oget _ Hcoins) /=.
  case (KEMROM.RO.RO.m{2}.[m{2}, pkh B1x2._pk{2}] = None) => Haux; split; try exact Hdom.
  by move=> mm hh; rewrite get_setE Hmap /=; case (hh = pkh B1x2._pk{2}) => Hh /=.
  exact Hmap.
  rcondf{2} 5; first by auto.
  wp; rnd; wp; skip.
  move=> &1 &2 [[Hx [Hdom Hmap]] Hpk] /=; move=> [kk rr] Hsupp; rewrite Hx !domE Hmap Hpk /=; case (KEMROM.RO.RO.m{2}.[m{2}, hpk{2}] = None) => Hfresh; rewrite /= ?get_set_sameE /=.
  split; first exact Hdom.
  move=> mm hh; rewrite !get_setE Hmap /=; case (hh = pkh B1x2._pk{2}) => Hh /=; last by [].
  by rewrite Hh (eq_sym (pkh B1x2._pk{2}) hpk{2}) Hpk /=.
  split; first by case: (oget KEMROM.RO.RO.m{2}.[m{2}, hpk{2}]).
  split; [exact Hdom | exact Hmap].
qed.

lemma mlkem_cpa_prg_middle &m :
  Pr[PRG_KG.IND(PRG_KG.PRGi, D_KG(QP)).main() @ &m : res] =
  Pr[PRG_ENC.IND(PRG_ENC.PRGr, D_ENC(QP)).main() @ &m : res].
proof.
  byequiv (_ : ={glob QP} ==> ={res}) => //.
  proc; inline *.
  swap{1} 9 -7.
  wp; call (_ : true); wp; rnd; call (_ : true); wp.
  rnd; wp; rnd; wp; rnd{1}; auto; smt(drand_ll).
qed.

module MlkemSamples = {
  proc kgdraw() : seed * vector * vector = {
    var sd, ss, ee;
    sd <$ dseed; ss <$ dshort; ee <$ dshort;
    return (sd,ss,ee);
  }
  proc encdraw() : vector * vector * R = {
    var rr, ee1, ee2;
    rr <$ dshort; ee1 <$ dshort; ee2 <$ dshort_R;
    return (rr,ee1,ee2);
  }
}.

lemma mlkem_kg_sample : equiv [PRG_KG.PRGi.get ~ MlkemSamples.kgdraw :
  true ==> ={res}].
proof.
  proc; rndsem*{2} 0; rnd; skip.
  by rewrite /prg_kg_ideal /=; move=> [sd ss ee] /= ->.
qed.

lemma mlkem_enc_sample : equiv [PRG_ENC.PRGi.get ~ MlkemSamples.encdraw :
  true ==> ={res}].
proof.
  proc; rndsem*{2} 0; rnd; skip.
  by rewrite /prg_enc_ideal /=; move=> [rr ee1 ee2] /= ->.
qed.

lemma mlkem_cpa_prg_ideal &m :
  Pr[PRG_ENC.IND(PRG_ENC.PRGi, D_ENC(QP)).main() @ &m : res] =
  Pr[TT.PKE.CPA(MLWE_PKE_HASH_PROC, QP).main() @ &m : res].
proof.
  byequiv (_ : ={glob QP} ==> ={res}) => //.
  proc; inline *.
  swap{2} [11..13] -10.
  seq 1 0 : (={glob QP}); first by rnd{1}; skip; smt(drand_ll).
  sp.
  seq 1 3 : (={glob QP} /\ r{1} = (r,e1,e2){2}).
  + rndsem*{2} 0; rnd; skip; rewrite /prg_enc_ideal /=; progress.
    by clear H H0; case rL.
  wp; call (_ : true); wp; rnd; call (_ : true); wp.
  rndsem*{2} 0; rnd; wp; skip; rewrite /prg_kg_ideal /=; progress; smt().
qed.
lemma mlkem_real_triangle (zz xx yy : real) :
  `|xx - yy| <= `|xx - zz| + `|zz - yy|.
proof. smt(). qed.

lemma mlkem_cpa_bound &m kgB encB :
  islossless QP.choose => islossless QP.guess =>
  `|Pr[PRG_KG.IND(PRG_KG.PRGr, D_KG(QP)).main() @ &m : res] -
    Pr[PRG_KG.IND(PRG_KG.PRGi, D_KG(QP)).main() @ &m : res]| <= kgB =>
  `|Pr[PRG_ENC.IND(PRG_ENC.PRGr, D_ENC(QP)).main() @ &m : res] -
    Pr[PRG_ENC.IND(PRG_ENC.PRGi, D_ENC(QP)).main() @ &m : res]| <= encB =>
  `|Pr[TT.PKE.CPA(MLWE_PKE_HASH, QP).main() @ &m : res] - 1%r/2%r| <=
  `|Pr[MLWE_H(B1(QP)).main(false, false) @ &m : res] -
    Pr[MLWE_H(B1(QP)).main(false, true) @ &m : res]| +
  `|Pr[MLWE_H(B2(QP)).main(true, false) @ &m : res] -
    Pr[MLWE_H(B2(QP)).main(true, true) @ &m : res]| + kgB + encB.
proof.
  move=> qcll qgll hkg henc.
  have hz : Pr[TT.PKE.CPA(MLWE_PKE_HASH2, QP).main() @ &m : res] = 1%r/2%r.
  + rewrite mlkem_uniform_pad; exact (mlkem_uniform_half &m qcll qgll).
  have h0 := mlkem_cpa_prg_real &m.
  have h1 := mlkem_cpa_prg_middle &m.
  have h2 := mlkem_cpa_prg_ideal &m.
  have h3 := mlkem_cpa_mlwe_first &m.
  have h4 := mlkem_cpa_mlwe_first_random &m.
  have h5 := mlkem_cpa_mlwe_second &m.
  have h6 := mlkem_cpa_mlwe_second_random &m.
  have ht0 := mlkem_real_triangle
    Pr[PRG_KG.IND(PRG_KG.PRGi, D_KG(QP)).main() @ &m : res]
    Pr[TT.PKE.CPA(MLWE_PKE_HASH, QP).main() @ &m : res]
    Pr[TT.PKE.CPA(MLWE_PKE_HASH2, QP).main() @ &m : res].
  have ht1 := mlkem_real_triangle
    Pr[TT.PKE.CPA(MLWE_PKE_HASH_PROC, QP).main() @ &m : res]
    Pr[PRG_KG.IND(PRG_KG.PRGi, D_KG(QP)).main() @ &m : res]
    Pr[TT.PKE.CPA(MLWE_PKE_HASH2, QP).main() @ &m : res].
  have ht2 := mlkem_real_triangle
    Pr[TT.PKE.CPA(MLWE_PKE_HASH1, QP).main() @ &m : res]
    Pr[TT.PKE.CPA(MLWE_PKE_HASH_PROC, QP).main() @ &m : res]
    Pr[TT.PKE.CPA(MLWE_PKE_HASH2, QP).main() @ &m : res].
  smt().
qed.
end section MlkemCPA.

section MlkemCorrectnessPRG.
declare module QCR <: TT.PKE.CORR_ADV{-MLWE_PKE_HASH_PRG, -CB}.

lemma mlkem_corr_prg_real &m :
  Pr[TT.PKE.Correctness_Adv(MLWE_PKE_HASH, QCR).main() @ &m : res] =
  Pr[PRG_KG.IND(PRG_KG.PRGr, DC_KG(QCR)).main() @ &m : res].
proof.
  byequiv (_ : ={glob QCR} ==> ={res}) => //.
  proc; inline *.
  swap{1} 7 -3.
  wp; call (_ : true); wp; rnd; wp; rnd; auto.
  rewrite /kg /enc /=; smt().
qed.

lemma mlkem_corr_prg_middle &m :
  Pr[PRG_KG.IND(PRG_KG.PRGi, DC_KG(QCR)).main() @ &m : res] =
  Pr[PRG_ENC.IND(PRG_ENC.PRGr, DC_ENC(QCR)).main() @ &m : res].
proof.
  byequiv (_ : ={glob QCR} ==> ={res}) => //.
  proc; inline *.
  swap{1} 9 -7.
  wp; call (_ : true); wp; rnd; wp; rnd; wp; rnd{1}; auto; smt(drand_ll).
qed.

lemma mlkem_corr_prg_ideal &m :
  Pr[PRG_ENC.IND(PRG_ENC.PRGi, DC_ENC(QCR)).main() @ &m : res] =
  Pr[TT.PKE.Correctness_Adv(MLWE_PKE_HASH_PROC, QCR).main() @ &m : res].
proof.
  byequiv (_ : ={glob QCR} ==> ={res}) => //.
  proc; inline *.
  swap{2} [10..12] -9.
  seq 1 0 : (={glob QCR}); first by rnd{1}; skip; smt(drand_ll).
  sp.
  seq 1 3 : (={glob QCR} /\ r{1} = (r,e1,e2){2}).
  + rndsem*{2} 0; rnd; skip; rewrite /prg_enc_ideal /=; progress.
    by clear H H0; case rL.
  wp; call (_ : true); wp.
  rndsem*{2} 0; rnd; wp; skip; rewrite /prg_kg_ideal /dec /=; progress; smt().
qed.
lemma mlkem_correctness_bound &m fb kgB encB :
  islossless QCR.find =>
  Pr[CorrectnessBound.main() @ &m : res] <= fb =>
  `|Pr[PRG_KG.IND(PRG_KG.PRGr, DC_KG(QCR)).main() @ &m : res] -
    Pr[PRG_KG.IND(PRG_KG.PRGi, DC_KG(QCR)).main() @ &m : res]| <= kgB =>
  `|Pr[PRG_ENC.IND(PRG_ENC.PRGr, DC_ENC(QCR)).main() @ &m : res] -
    Pr[PRG_ENC.IND(PRG_ENC.PRGi, DC_ENC(QCR)).main() @ &m : res]| <= encB =>
  Pr[TT.PKE.Correctness_Adv(MLWE_PKE_HASH, QCR).main() @ &m : res] <= fb + kgB + encB.
proof.
  move=> qll hf hkg henc.
  have hn := mlkem_ideal_correctness QCR &m qll.
  have h0 := mlkem_corr_prg_real &m.
  have h1 := mlkem_corr_prg_middle &m.
  have h2 := mlkem_corr_prg_ideal &m.
  smt().
qed.
end section MlkemCorrectnessPRG.

lemma mlkem_base_keygen : equiv [TT.BasePKE.kg ~ MLWE_PKE_HASH.kg :
  true ==> ={res}].
proof.
  proc; rndsem*{2} 0; rnd; skip.
  have he : (fun rr => ((kg rr).`1, (kg rr).`2)) = kg.
  + by apply fun_ext => rr; case (kg rr).
  by rewrite /TT.kg he /=; move=> [pk sk] /= ->.
qed.

lemma mlkem_base_encrypt : equiv [TT.BasePKE.enc ~ MLWE_PKE_HASH.enc :
  ={arg} ==> ={res}].
proof. by proc; inline *; auto. qed.

lemma mlkem_base_decrypt : equiv [TT.BasePKE.dec ~ MLWE_PKE_HASH.dec :
  ={arg} ==> ={res}].
proof. by proc; inline *; auto. qed.

lemma mlkem_base_cpa (QB <: TT.PKE.Adversary) &m :
  Pr[TT.PKE.CPA(TT.BasePKE, QB).main() @ &m : res] =
  Pr[TT.PKE.CPA(MLWE_PKE_HASH, QB).main() @ &m : res].
proof.
  byequiv (_ : ={glob QB} ==> ={res}) => //.
  proc; call (_ : true); call mlkem_base_encrypt; rnd;
    call (_ : true); call mlkem_base_keygen; auto.
qed.

lemma mlkem_base_corr (QB <: TT.PKE.CORR_ADV) &m :
  Pr[TT.PKE.Correctness_Adv(TT.BasePKE, QB).main() @ &m : res] =
  Pr[TT.PKE.Correctness_Adv(MLWE_PKE_HASH, QB).main() @ &m : res].
proof.
  byequiv (_ : ={glob QB} ==> ={res}) => //.
  proc; call mlkem_base_decrypt; call mlkem_base_encrypt;
    call (_ : true); call mlkem_base_keygen; auto.
qed.
lemma mlkem_split_decap (pp : pkey) :
  equiv [FO_K(KEMROM.RO.RO).dec ~
    UU_L(KEMROMx2.RO1.RO, KEMROMx2.RO2.RO).dec :
    ={arg} /\ sk{2}.`1.`1 = pp /\
    mlkem_split_map pp KEMROM.RO.RO.m{1} KEMROM.RO.RO.m{2}
      KEMROMx2.RO1.RO.m{2} KEMROMx2.RO2.RO.m{2}
    ==>
    ={res} /\
    mlkem_split_map pp KEMROM.RO.RO.m{1} KEMROM.RO.RO.m{2}
      KEMROMx2.RO1.RO.m{2} KEMROMx2.RO2.RO.m{2}].
proof.
(* COMPLETE THIS *)
  proc; inline *; sp.
  swap{2} 5 -4; seq 1 2 : (#pre /\ r0{1} = (r3{2}, r2{2})).
  rndsem*{2} 0; auto; rewrite -dprod_dlet; auto.
  by smt().
  seq 1 4 : (={sk,c,m'} /\ sk{2}.`1.`1 = pp /\ rv{2} = None /\ x{1} = (oget m'{2}, pkh pp) /\ mlkem_split_map pp KEMROM.RO.RO.m{1} KEMROM.RO.RO.m{2} KEMROMx2.RO1.RO.m{2} KEMROMx2.RO2.RO.m{2} /\ oget m'{2} \in KEMROMx2.RO1.RO.m{2} /\ oget m'{2} \in KEMROMx2.RO2.RO.m{2}).
  auto.
  rewrite /mlkem_split_map; smt(FMap.domE get_setE none_omap).
  auto; rewrite /mlkem_split_map.
  if{2}.
  rcondf{2} 3; first by auto.
  swap{2} 2 -1; seq 0 1 : (#pre); first by rnd{2}; auto; smt(drand_ll).
  sp; if{2}; first by auto; smt(FMap.domE oget_omap_some).
  rcondf{2} 3; first by auto; smt().
  wp; rnd{2}; wp; skip; smt(dkey_ll FMap.domE oget_omap_some).
  rcondt{2} 1; first by auto; smt().
  by auto; smt().
qed.
section MlkemOneWay.
declare module QW <: TT.PKE.OW_CPA_ADV{-TT.PKE.OW_CPA, -TT.PKE.BOWp,
  -TT.PKE.OWL_CPA, -TT.PKE.OWvsIND.Bowl}.

lemma mlkem_ow_good &m :
  Pr[TT.PKE.OW_CPA(TT.BasePKE, QW).main() @ &m :
    res /\ dec TT.PKE.OW_CPA.sk TT.PKE.OW_CPA.cc = Some TT.PKE.OW_CPA.m] <=
  Pr[TT.PKE.OW_CPA(TT.BasePKE, QW).main_perfect() @ &m : res].
proof.
  byequiv (_ : ={glob QW} ==>
    (res{1} /\ dec TT.PKE.OW_CPA.sk{1} TT.PKE.OW_CPA.cc{1} = Some TT.PKE.OW_CPA.m{1})
    => res{2}) => //.
  proc; inline *; wp; call (_ : true); auto; smt().
qed.

lemma mlkem_ow_bad &m :
  islossless QW.find =>
  Pr[TT.PKE.OW_CPA(TT.BasePKE, QW).main() @ &m :
    dec TT.PKE.OW_CPA.sk TT.PKE.OW_CPA.cc <> Some TT.PKE.OW_CPA.m] =
  Pr[TT.PKE.Correctness_Adv(TT.BasePKE, TT.PKE.BOWp(TT.BasePKE, QW)).main() @ &m : res].
proof.
  move=> qll.
  byequiv (_ : true ==>
    (dec TT.PKE.OW_CPA.sk{1} TT.PKE.OW_CPA.cc{1} <> Some TT.PKE.OW_CPA.m{1}) = res{2}) => //.
  proc; inline *; wp; call{1} qll; auto; smt().
qed.

lemma mlkem_ow_list_singleton &m :
  Pr[TT.PKE.OW_CPA(TT.BasePKE, QW).main_perfect() @ &m : res] =
  Pr[TT.PKE.OWL_CPA(TT.BasePKE, TT.PKE.OWvsIND.BL(QW)).main() @ &m : res].
proof.
  byequiv (_ : ={glob QW} ==> ={res}) => //.
  proc; inline *; wp; call (_ : true); auto.
  progress.
  by case result_R=> //= mm; smt().
qed.

lemma mlkem_ow_to_list &m :
  islossless QW.find =>
  Pr[TT.PKE.OW_CPA(TT.BasePKE, QW).main() @ &m : res] <=
  Pr[TT.PKE.OWL_CPA(TT.BasePKE, TT.PKE.OWvsIND.BL(QW)).main() @ &m : res] +
  Pr[TT.PKE.Correctness_Adv(TT.BasePKE, TT.PKE.BOWp(TT.BasePKE, QW)).main() @ &m : res].
proof.
  move=> qll.
  have hg := mlkem_ow_good &m.
  have hb := mlkem_ow_bad &m qll.
  have hl := mlkem_ow_list_singleton &m.
  rewrite Pr[mu_split (dec TT.PKE.OW_CPA.sk TT.PKE.OW_CPA.cc = Some TT.PKE.OW_CPA.m)].
  have hm : Pr[TT.PKE.OW_CPA(TT.BasePKE, QW).main() @ &m :
      res /\ !(dec TT.PKE.OW_CPA.sk TT.PKE.OW_CPA.cc = Some TT.PKE.OW_CPA.m)] <=
    Pr[TT.PKE.OW_CPA(TT.BasePKE, QW).main() @ &m :
      dec TT.PKE.OW_CPA.sk TT.PKE.OW_CPA.cc <> Some TT.PKE.OW_CPA.m].
  + by rewrite Pr[mu_sub].
  smt().
qed.
end section MlkemOneWay.

lemma mlkem_plaintext_mass mm : mu1 TT.dplaintext mm = TT.PKE.eps_msg.
proof.
  rewrite (mu1_uni_ll TT.dplaintext mm TT.dplaintext_uni TT.dplaintext_ll)
    TT.dplaintext_fu /=.
  have hs : support TT.dplaintext = predT.
  + by apply fun_ext => xx; rewrite TT.dplaintext_fu.
  by rewrite hs -TT.FinT.card_size_to_seq /TT.PKE.eps_msg
    /TT.PKE.MFinT.card /TT.FinT.card.
qed.

lemma mlkem_plaintext_list_mass (ll : plaintext list) :
  mu TT.dplaintext (mem ll) <= (size ll)%r * TT.PKE.eps_msg.
proof.
  apply mu_mem_le_mu1 => mm; by rewrite mlkem_plaintext_mass.
qed.
lemma mlkem_split_countget (QD <: KEMROMx2.CCA_ORC) :
  equiv [KEMROM.RO.RO.get ~
    CountH(B1x2(A, KEMROMx2.RO_x2(KEMROMx2.RO1.RO, KEMROMx2.RO2.RO), QD).BH).get :
    ={arg} /\
    mlkem_split_map B1x2._pk{2} KEMROM.RO.RO.m{1} KEMROM.RO.RO.m{2}
      KEMROMx2.RO1.RO.m{2} KEMROMx2.RO2.RO.m{2}
    ==>
    ={res} /\
    mlkem_split_map B1x2._pk{2} KEMROM.RO.RO.m{1} KEMROM.RO.RO.m{2}
      KEMROMx2.RO1.RO.m{2} KEMROMx2.RO2.RO.m{2}].
proof.
  proc*; inline{2} CountH(B1x2(A, KEMROMx2.RO_x2(KEMROMx2.RO1.RO, KEMROMx2.RO2.RO), QD).BH).get.
  wp; call (mlkem_split_get QD); auto.
qed.

module MlkemCCALOracle = CCAL(KEMROMx2.RO1.RO, KEMROMx2.RO2.RO, B1x2(A)).O.

lemma mlkem_split_cca &m :
  Pr[KEMROM.CCA(KEMROM.RO.RO, FO_K, A).main() @ &m : res] =
  Pr[CCAL(KEMROMx2.RO1.RO, KEMROMx2.RO2.RO, B1x2(A)).main() @ &m : res].
proof.
(* COMPLETE THIS *)
  byequiv (_ : ={glob A} ==> ={res}) => //.
  proc; inline *.
  wp; call (_ :
    ={KEMROM.CCA.cstar, KEMROM.CCA.sk} /\
    B1x2._pk{2} = KEMROM.CCA.sk{2}.`1.`1 /\
    mlkem_split_map B1x2._pk{2} KEMROM.RO.RO.m{1} KEMROM.RO.RO.m{2}
      KEMROMx2.RO1.RO.m{2} KEMROMx2.RO2.RO.m{2}).
  + proc; sp; if; first by auto.
  - by exlim B1x2._pk{2} => pp; wp; call (mlkem_split_decap pp); auto; smt().
  by auto.
  + proc*; call (mlkem_split_countget MlkemCCALOracle); auto.
  rcondt{1} 12; first auto.
  by smt(mem_empty).
  rcondt{2} 15; first by auto; smt(mem_empty).
  rcondt{2} 21; first by auto; smt(mem_empty).
  swap{2} 20 -6; wp 11 15; rndsem*{2} 13.
  auto => />.
  rewrite /dmap -!dprod_dlet; progress; rewrite !get_setE !emptyE /=.
  by [].
  by [].
  by [].
  by move: H6; rewrite get_setE emptyE; case: (mm = mL).
  by move: H6; rewrite get_setE emptyE; case: (mm = mL).
  case: (mm = mL); case: (hh = pkh pk0skL.`1) => /=.
  by smt().
  by [].
  by [].
  by [].
qed.
module MlkemListCanon(QQ : TT.PKE.OWL_CPA_ADV) = {
  proc run() : plaintext * plaintext * plaintext list = {
    var pk, sk, mc, mo, cc, ll;
    (pk,sk) <@ TT.BasePKE.kg();
    mc <$ TT.dplaintext;
    cc <@ TT.BasePKE.enc(pk,mc);
    ll <@ QQ.find(pk,cc);
    mo <$ TT.dplaintext;
    return (mc,mo,ll);
  }
  proc main() : bool = {
    var mc, mo, ll, zz;
    (mc,mo,ll) <@ run();
    zz <$ DBool.dbool;
    return if (mc \in ll = mo \in ll) then zz else mc \in ll;
  }
}.

module MlkemListMix(QQ : TT.PKE.OWL_CPA_ADV) = {
  proc main() : bool = {
    var mc, mo, ll, zz;
    (mc,mo,ll) <@ MlkemListCanon(QQ).run();
    zz <$ DBool.dbool;
    return if zz then mc \in ll else !(mo \in ll);
  }
}.

module MlkemListTrue(QQ : TT.PKE.OWL_CPA_ADV) = {
  proc main(uu : unit) : bool = {
    var out;
    out <@ MlkemListCanon(QQ).run();
    return out.`1 \in out.`3;
  }
}.

module MlkemListOther(QQ : TT.PKE.OWL_CPA_ADV) = {
  proc main(uu : unit) : bool = {
    var out;
    out <@ MlkemListCanon(QQ).run();
    return out.`2 \in out.`3;
  }
}.

section MlkemListIND.
declare module QL <: TT.PKE.OWL_CPA_ADV{-TT.PKE.OWL_CPA, -TT.PKE.OWvsIND.Bowl}.

lemma mlkem_list_true &m :
  Pr[MlkemListCanon(QL).run() @ &m : res.`1 \in res.`3] =
  Pr[TT.PKE.OWL_CPA(TT.BasePKE, QL).main() @ &m : res].
proof.
  byequiv (_ : ={glob QL} ==> (res{1}.`1 \in res{1}.`3) = res{2}) => //.
  proc; inline *; rnd{1}; wp; call (_ : true); auto; smt(TT.dplaintext_ll).
qed.

lemma mlkem_list_canonical &m :
  Pr[TT.PKE.CPA(TT.BasePKE, TT.PKE.OWvsIND.Bowl(QL)).main() @ &m : res] =
  Pr[MlkemListCanon(QL).main() @ &m : res].
proof.
  byequiv (_ : ={glob QL} ==> ={res}) => //.
  proc; inline *.
  swap{1} 8 -7; swap{1} 15 1; swap{2} 10 -7.
  seq 1 0 : (={glob QL}); first by rnd{1}; auto.
  case (b{1}).
  + wp; rnd; wp; call (_ : true); wp; rnd; wp; rnd; rnd; wp; rnd; skip; progress; smt().
  swap{2} 3 1.
  wp; rnd (fun zz => !zz); wp; call (_ : true); wp; rnd; wp; rnd; rnd; wp; rnd; skip; progress; smt().
qed.
lemma mlkem_list_mixed &m :
  Pr[MlkemListCanon(QL).main() @ &m : res] =
  Pr[MlkemListMix(QL).main() @ &m : res].
proof.
  byequiv (_ : ={glob QL} ==> ={res}) => //.
  proc; inline *; wp.
  rnd (fun zz => if mc{1} \in ll{1} then zz else !zz).
  wp; rnd; wp; call (_ : true); wp; rnd; wp; rnd; wp; rnd; skip; progress; smt().
qed.

local module MLT = MlkemListTrue(QL).
local module MLO = MlkemListOther(QL).

local lemma mlkem_list_randomlr &m :
  Pr[MlkemListMix(QL).main() @ &m : res] =
  Pr[TT.PKE.LorR.RandomLR(MLT, MLO).main() @ &m : res].
proof.
  byequiv (_ : ={glob QL} ==> ={res}) => //.
  proc; inline *.
  swap{1} 12 -11.
  seq 1 1 : (={glob QL} /\ zz{1} = b{2}); first by auto.
  if{2}; wp; rnd; wp; call (_ : true); auto; progress; smt().
qed.

local lemma mlkem_list_other_ll :
  islossless QL.find => islossless MLO.main.
proof.
  move=> qll; proc; inline *; islossless; smt(TT.kg_ll TT.dplaintext_ll drand_ll).
qed.

lemma mlkem_list_lr_gap &m :
  islossless QL.find =>
  `|Pr[MlkemListCanon(QL).run() @ &m : res.`1 \in res.`3] -
    Pr[MlkemListCanon(QL).run() @ &m : res.`2 \in res.`3]| =
  2%r * `|Pr[TT.PKE.CPA(TT.BasePKE, TT.PKE.OWvsIND.Bowl(QL)).main() @ &m : res] - 1%r/2%r|.
proof.
  move=> qll.
  have hll : Pr[MLO.main() @ &m : true] = 1%r.
  + byphoare (mlkem_list_other_ll qll) => //.
  have hh := TT.PKE.LorR.pr_AdvLR_AdvRndLR MLT MLO &m () hll.
  rewrite mlkem_list_canonical mlkem_list_mixed mlkem_list_randomlr.
  have ht : Pr[MLT.main() @ &m : res] =
    Pr[MlkemListCanon(QL).run() @ &m : res.`1 \in res.`3].
  + byequiv (_ : ={glob QL} ==> res{1} = (res{2}.`1 \in res{2}.`3)) => //.
    proc; inline *; wp; rnd; wp; call (_ : true); auto.
  have ho : Pr[MLO.main() @ &m : res] =
    Pr[MlkemListCanon(QL).run() @ &m : res.`2 \in res.`3].
  + byequiv (_ : ={glob QL} ==> res{1} = (res{2}.`2 \in res{2}.`3)) => //.
    proc; inline *; wp; rnd; wp; call (_ : true); auto.
  smt().
qed.
lemma mlkem_list_other_bound &m qb :
  0 <= qb => islossless QL.find =>
  hoare [QL.find : true ==> size res <= qb] =>
  Pr[MlkemListCanon(QL).run() @ &m : res.`2 \in res.`3] <= qb%r * TT.PKE.eps_msg.
proof.
  move=> hq qll hsz.
  have heps : 0%r <= TT.PKE.eps_msg.
  + by have := ge0_mu1 TT.dplaintext witness; rewrite mlkem_plaintext_mass.
  byphoare (_ : true ==> res.`2 \in res.`3) => //.
  proc.
  seq 4 : (size ll <= qb) 1%r (qb%r * TT.PKE.eps_msg) 0%r 0%r => //.
  + rnd (mem ll); skip; progress.
    have hh := mlkem_plaintext_list_mass ll{hr}.
    have hb : (size ll{hr})%r <= qb%r by rewrite Real.le_fromint.
    have hm := StdOrder.RealOrder.ler_wpmul2r _ heps _ _ hb.
    exact (StdOrder.RealOrder.ler_trans _ _ _ hh hm).
  hoare; conseq (_ : true ==> size ll <= qb) => //.
  call hsz; inline *; auto.
qed.

lemma mlkem_list_to_ind &m qb :
  0 <= qb => islossless QL.find =>
  hoare [QL.find : true ==> size res <= qb] =>
  Pr[TT.PKE.OWL_CPA(TT.BasePKE, QL).main() @ &m : res] <=
  2%r * `|Pr[TT.PKE.CPA(TT.BasePKE, TT.PKE.OWvsIND.Bowl(QL)).main() @ &m : res] - 1%r/2%r| +
    qb%r * TT.PKE.eps_msg.
proof.
  move=> hq qll hsz.
  have ht := mlkem_list_true &m.
  have hg := mlkem_list_lr_gap &m qll.
  have hb := mlkem_list_other_bound &m qb hq qll hsz.
  smt().
qed.
end section MlkemListIND.

lemma mlkem_lazy_second &m :
  Pr[CCAL(KEMROMx2.RO1.RO, KEMROMx2.RO2.RO, B1x2(A)).main() @ &m : res] =
  Pr[CCAL(KEMROMx2.RO1.RO, KEMROMx2.RO2.LRO, B1x2(A)).main() @ &m : res].
proof.
  byequiv (KEMROMx2.RO2.FullEager.RO_LRO_D (DKK2(B1x2(A))) _) => //.
  by move=> x; apply dkey_ll.
qed.

lemma mlkem_lazy_first &m :
  Pr[CCAL(KEMROMx2.RO1.RO, KEMROMx2.RO2.LRO, B1x2(A)).main() @ &m : res] =
  Pr[CCAL(KEMROMx2.RO1.LRO, KEMROMx2.RO2.LRO, B1x2(A)).main() @ &m : res].
proof.
  byequiv (KEMROMx2.RO1.FullEager.RO_LRO_D (DKK1(B1x2(A))) _) => //.
  by move=> x; apply drand_ll.
qed.

lemma mlkem_lazy_cca : equiv [
  CCAL(KEMROMx2.RO1.LRO, KEMROMx2.RO2.LRO, B1x2(A)).main ~
  KEMROMx2.CCA(KEMROMx2.RO_x2(KEMROMx2.RO1.RO,KEMROMx2.RO2.RO), UU, B1x2(A)).main :
  ={glob A} ==> ={res}].
proof.
  proc; inline *; wp.
  call (_ : KEMROM.CCA.sk{1} = KEMROMx2.CCA.sk{2} /\
    KEMROM.CCA.cstar{1} = KEMROMx2.CCA.cstar{2} /\
    ={KEMROMx2.RO1.RO.m, KEMROMx2.RO2.RO.m, KEMROM.RO.RO.m, B1x2._pk}).
  + proc; sp; if; first by auto.
    - inline *.
      seq 7 8 : (={rv, sk, c0, KEMROMx2.RO1.RO.m, KEMROMx2.RO2.RO.m,
                    KEMROM.RO.RO.m, B1x2._pk} /\
        KEMROM.CCA.sk{1} = KEMROMx2.CCA.sk{2} /\
        KEMROM.CCA.cstar{1} = KEMROMx2.CCA.cstar{2} /\
        (rv{1} <> None => rv{1} = m'{1})).
      + sp; if; first by auto.
        - by auto; progress; smt().
        by auto.
      sp; if; first by auto.
      + by auto.
      by auto; progress; smt().
    by auto.
  + by proc; inline *; sim.
  auto; progress; smt().
qed.

lemma mlkem_u_prf_real : equiv [
  KEMROMx2.CCA(KEMROMx2.RO_x2(KEMROMx2.RO1.RO,KEMROMx2.RO2.RO), UU, B1x2(A)).main ~
  J.IND(PseudoRF.PRF, D(B1x2(A))).main :
  ={glob A} ==> ={res}].
proof.
(* COMPLETE THIS *)
  proc; inline *; wp.
  call (_ : ={KEMROMx2.RO1.RO.m, KEMROMx2.RO2.RO.m, KEMROM.RO.RO.m, B1x2._pk,
               KEMROMx2.CCA.cstar} /\
    KEMROMx2.CCA.sk{1}.`1 = KEMROMx2.CCA.sk{2}.`1 /\
    KEMROMx2.CCA.sk{1}.`2 = PseudoRF.PRF.k{2}).
  proc; inline *.
  sp 1 1; if; first by auto.
  sp 7 7; if; first by auto => />; smt().
  seq 7 7 : (={m', c0, KEMROMx2.RO1.RO.m, KEMROMx2.RO2.RO.m, KEMROM.RO.RO.m, B1x2._pk, KEMROMx2.CCA.cstar} /\ sk{1}.`2 = PseudoRF.PRF.k{2} /\ KEMROMx2.CCA.sk{1}.`1 = KEMROMx2.CCA.sk{2}.`1 /\ KEMROMx2.CCA.sk{1}.`2 = PseudoRF.PRF.k{2}).
  wp; sp 1 1; seq 1 1 : (={r1, sk0, c1, m'0, c0, KEMROMx2.RO1.RO.m, KEMROMx2.RO2.RO.m, KEMROM.RO.RO.m, B1x2._pk, KEMROMx2.CCA.cstar} /\ x0{1} = x1{2} /\ sk{1}.`2 = PseudoRF.PRF.k{2} /\ KEMROMx2.CCA.sk{1}.`1 = KEMROMx2.CCA.sk{2}.`1 /\ KEMROMx2.CCA.sk{1}.`2 = PseudoRF.PRF.k{2}); first by rnd; skip; smt().
  by skip; smt().
  if; [by auto => /> | by auto => />; smt() | by wp; rnd; wp; skip; smt()].
  sp 1 1; if; [by auto => />; smt() | by auto => />; smt() | by exfalso; auto => />; smt()].
  by auto => />.
  proc; inline *.
  conseq (_ : ={x, KEMROMx2.RO1.RO.m, KEMROMx2.RO2.RO.m, KEMROM.RO.RO.m, B1x2._pk, KEMROMx2.CCA.cstar} ==> ={r, KEMROMx2.RO1.RO.m, KEMROMx2.RO2.RO.m, KEMROM.RO.RO.m, B1x2._pk, KEMROMx2.CCA.cstar}); first 2 by smt().
  by sim.
  swap{2} 1 4; auto => />; smt().
qed.

lemma mlkem_u_prf_random &m :
  Pr[J.IND(RF.RF, D(B1x2(A))).main() @ &m : res] =
  Pr[Gm1(KEMROMx2.RO_x2(KEMROMx2.RO1.RO,KEMROMx2.RO2.RO), B1x2(A)).main() @ &m : res].
proof. by byequiv => //; sim. qed.

module MlkemUEager(QQ : KEMROMx2.CCA_ADV, G : KEMROMx2.RO1.RO) = {
  module Hx = {
    proc init() = { KEMROMx2.RO2.RO.init(); }
    proc get1 = G.get
    proc get2 = KEMROMx2.RO2.RO.get
  }
  proc distinguish = Gm1(Hx, QQ).main
}.

lemma mlkem_u_eager &m :
  Pr[Gm1(KEMROMx2.RO_x2(KEMROMx2.RO1.RO,KEMROMx2.RO2.RO), B1x2(A)).main() @ &m : res] =
  Pr[Gm1(RO_x2E, B1x2(A)).main() @ &m : res].
proof.
  have hll : forall (x : plaintext), is_lossless drand by move=> x; apply drand_ll.
  have h1 := RO1E.pr_RO_FinRO_D hll (MlkemUEager(B1x2(A))) &m () (fun b => b).
  have h2 := RO1E.pr_FinRO_FunRO_D hll (MlkemUEager(B1x2(A))) &m () (fun b => b).
  have hl : Pr[Gm1(KEMROMx2.RO_x2(KEMROMx2.RO1.RO,KEMROMx2.RO2.RO), B1x2(A)).main() @ &m : res] =
    Pr[KEMROMx2.RO1.MainD(MlkemUEager(B1x2(A)),KEMROMx2.RO1.RO).distinguish() @ &m : res].
  + byequiv => //; proc; inline *; swap{2} 1 1; sim; auto; progress; smt().
  have hr : Pr[Gm1(RO_x2E, B1x2(A)).main() @ &m : res] =
    Pr[KEMROMx2.RO1.MainD(MlkemUEager(B1x2(A)),RO1E.FunRO).distinguish() @ &m : res].
  + byequiv => //; proc; inline *; swap{2} 1 1; sim; auto; progress; smt().
  smt().
qed.

op mlkem_u_inv (ss : pkey * MLWE_PKE_Hash.skey) (ff : plaintext -> randomness)
    (hl hr : (plaintext, key) fmap) (fm : (ciphertext, key) fmap)
    (ll : (ciphertext * key) list) =
  (forall cc, assoc ll cc =
    if goodc cc ss ff then hl.[oc2m cc ss] else fm.[cc]) /\
  (forall mm, mm \in hl => dec ss.`2 (enc (ff mm) ss.`1 mm) = Some mm) /\
  (forall mm, mm \in hr => hl.[mm] = hr.[mm]).

lemma mlkem_u_good_enc (ss : pkey * MLWE_PKE_Hash.skey) ff mm :
  dec ss.`2 (enc (ff mm) ss.`1 mm) = Some mm =>
  goodc (enc (ff mm) ss.`1 mm) ss ff /\
  oc2m (enc (ff mm) ss.`1 mm) ss = mm.
proof. by rewrite /goodc /m2c /oc2m /c2m => ->. qed.

lemma mlkem_dec_nonempty ss cc : dec ss cc <> None.
proof. by rewrite /dec /=; case (c_decode cc). qed.

lemma mlkem_u_cipher_eq (ss : pkey * MLWE_PKE_Hash.skey) ff cc mm :
  goodc cc ss ff => oc2m cc ss = mm => cc = enc (ff mm) ss.`1 mm.
proof. rewrite /goodc /m2c; move=> [_ hc] <-; by rewrite hc. qed.

lemma mlkem_u_inv_empty (ss : pkey * MLWE_PKE_Hash.skey) ff :
  mlkem_u_inv ss ff empty empty empty [].
proof. by rewrite /mlkem_u_inv; smt(assoc_nil emptyE mem_empty). qed.

section MlkemUFairKeys.
declare module QF <: KEMROMx2.CCA_ADV{
  -KEMROMx2.CCA, -RO1E.FunRO, -KEMROMx2.RO1.RO, -KEMROMx2.RO2.RO,
  -RF.RF, -UU2, -H1, -H2, -Gm2, -Gm3, -H2BOWMod, -CountHx2}.

lemma mlkem_u_fair_keys : equiv [
  Gm3(H2(RO1E.FunRO), UU2, QF).main ~
  Gm3(H2(RO1E.FunRO), UU2, QF).main_0adv :
  ={glob QF} ==> ={res}].
proof.
  proc.
  swap{1} 11 -2.
  swap{2} 19 -10.
  seq 9 9 : (={glob QF, pk, b, H1.bad, H2.merr, H2.invert,
    RF.RF.m, RO1E.FunRO.f, KEMROMx2.RO2.RO.m, UU2.lD,
    KEMROMx2.CCA.sk, KEMROMx2.CCA.cstar}).
  + by inline *; sim.
  wp; rnd.
  call (_ : ={RO1E.FunRO.f, KEMROMx2.RO2.RO.m, UU2.lD,
    KEMROMx2.CCA.sk, KEMROMx2.CCA.cstar, H1.bad,
    H2.merr, H2.invert, H2.mtgt}).
  + by proc; inline *; sim.
  + by proc; inline *; sim.
  + by proc; inline *; sim.
  inline *; wp; rnd.
  case (b{1}).
  + rnd{1}; rnd; skip; progress; smt(dkey_ll).
  rnd; rnd{1}; skip; progress; smt(dkey_ll).
qed.
end section MlkemUFairKeys.

lemma mlkem_u_inv_good_lookup ss ff hl hr fm ll mm :
  mlkem_u_inv ss ff hl hr fm ll =>
  dec ss.`2 (enc (ff mm) ss.`1 mm) = Some mm =>
  assoc ll (enc (ff mm) ss.`1 mm) = hl.[mm].
proof.
  move=> hi hc.
  have [hg hd] := mlkem_u_good_enc ss ff mm hc.
  move: hi; rewrite /mlkem_u_inv; move=> [ha _].
  by rewrite (ha (enc (ff mm) ss.`1 mm)) hg hd.
qed.

lemma mlkem_u_inv_good_extend ss ff hl hr fm ll mm kk :
  mlkem_u_inv ss ff hl hr fm ll =>
  dec ss.`2 (enc (ff mm) ss.`1 mm) = Some mm =>
  hl.[mm] = None =>
  mlkem_u_inv ss ff hl.[mm <- kk] hr fm ((enc (ff mm) ss.`1 mm,kk) :: ll).
proof.
  rewrite /mlkem_u_inv; move=> [ha [hv hs]] hc hm.
  have [hg hd] := mlkem_u_good_enc ss ff mm hc.
  split.
  + move=> cc; rewrite List.assoc_cons FMap.get_setE.
    case (cc = enc (ff mm) ss.`1 mm) => he.
    + by rewrite he hg hd /=.
    have hn : goodc cc ss ff => oc2m cc ss <> mm by smt(mlkem_u_cipher_eq).
    have hh := ha cc; smt().
  split.
  + move=> xx; rewrite FMap.domE FMap.get_setE.
    case (xx = mm) => he; smt(FMap.domE).
  move=> xx hx; rewrite FMap.get_setE.
  have hh := hs xx hx.
  case (xx = mm) => he; smt(FMap.domE).
qed.

lemma mlkem_u_sim_decap (ss : pkey * MLWE_PKE_Hash.skey) : equiv [
  UU1(RF.RF, H1).dec ~ UU2(H2(RO1E.FunRO)).dec :
  ={arg, RO1E.FunRO.f} /\ sk{1}.`1 = ss /\
  KEMROMx2.CCA.sk{1}.`1 = ss /\ !H1.bad{1} /\ !H1.bad{2} /\
  mlkem_u_inv ss RO1E.FunRO.f{1} KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2}
    RF.RF.m{1} UU2.lD{2}
  ==> ={res} /\ !H1.bad{1} /\ !H1.bad{2} /\
  mlkem_u_inv ss RO1E.FunRO.f{1} KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2}
    RF.RF.m{1} UU2.lD{2}].
proof.
proc; inline *.
sp 5 1; if{1}; last by exfalso; auto; smt(mlkem_dec_nonempty).
sp 5 0; if{1}.
sp 1 0; if{2}.
rcondf{1} 1.
move=> &m; skip.
move=> &hr H.
case H => -[Hx [Hex Hnone]] Hcache.
case Hex => rvL [Hx0 [Hr [Hc' [Hrv [Hm' [Hpre Hne]]]]]].
case Hpre => Hko [Hk [Hsk0 [Hc0 [HrvL [Hdec [[Harg Hf] [Hss [Hcca [Hb1 [Hb2 Hinv]]]]]]]]]].
have Hbad : !goodc c{hr} ss RO1E.FunRO.f{hr} by rewrite /goodc /c2m /m2c /oc2m; smt().
move: Hinv; rewrite /mlkem_u_inv; move=> [Hlookup Hrest].
have Heq := Hlookup c{hr}; move: Heq; rewrite Hbad /=; move=> Heq; rewrite Hx domE.
move: Harg => /= Harg.
case Harg => Hsk Hc; rewrite -Heq Hc; exact Hcache.
auto; rewrite /mlkem_u_inv /goodc /c2m /m2c /oc2m /=; smt().
rcondt{1} 1.
move=> &m; skip; rewrite /mlkem_u_inv /goodc /c2m /m2c /oc2m /=.
smt(FMap.domE).
wp; rnd; skip; rewrite /mlkem_u_inv /=.
move=> &1 &2 H r0L Hr0; rewrite FMap.get_set_sameE /=.
have Hbad : !goodc c{1} ss RO1E.FunRO.f{1} by rewrite /goodc /c2m /m2c /oc2m; smt().
split; first by smt().
split; first by smt().
split; last by smt().
move=> cc; rewrite List.assoc_cons FMap.get_setE.
smt().
sp 3 0.
conseq (_ : c{1} = c{2} /\ c{1} = enc (RO1E.FunRO.f{1} m{1}) ss.`1 m{1} /\ dec ss.`2 c{1} = Some m{1} /\ !H1.bad{1} /\ !H1.bad{2} /\ mlkem_u_inv ss RO1E.FunRO.f{1} KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2} RF.RF.m{1} UU2.lD{2} ==> _).
move=> &1 &2 [badL [Hm [Hcm [Hbad [Hex Hne]]]]].
case Hex => rvL [Hx0 [Hr [Hcp [Hrv [Hmp [Hpre Hnz]]]]]].
case Hpre => Hko [Hk [Hsk0 [Hc0 [HrvL [Hdec [[Harg Hf] [Hss [Hcca [Hb1 [Hb2 Hinv]]]]]]]]]].
have Hce : c0{1} = c'{1} by smt().
have Hmo : m'{1} = m'0{1} by smt().
have Hsome0 := some_oget m'0{1} Hnz.
have Hsome : m'0{1} = Some m{1} by smt().
have Hcipher : c{1} = enc (RO1E.FunRO.f{1} m{1}) ss.`1 m{1} by smt().
have Hcorrect : dec ss.`2 c{1} = Some m{1} by smt().
have Hcmc : cm{1} = c{1} by rewrite Hcm Hcca -Hcipher.
have Hnb : !H1.bad{1} by rewrite Hbad Hcca Hcmc Hcorrect /=.
split; first by move: Harg => /=; smt().
split; first exact Hcipher.
split; first exact Hcorrect.
split; first exact Hnb.
split; first exact Hb2.
exact Hinv.
if{2}.
+ rcondf{1} 2; first by auto; smt(mlkem_u_inv_good_lookup FMap.domE).
  wp; rnd{1}; skip.
  smt(dkey_ll mlkem_u_inv_good_lookup FMap.domE some_oget).
rcondt{1} 2; first by auto; smt(mlkem_u_inv_good_lookup FMap.domE).
wp; rnd; skip.
move=> &1 &2 [[he [hc [hd [hb1 [hb2 hi]]]]] hn] kk hk.
rewrite /= FMap.get_set_sameE /=.
split; first exact hb1.
split; first exact hb2.
have hcorrect : dec ss.`2 (enc (RO1E.FunRO.f{1} m{1}) ss.`1 m{1}) = Some m{1}
  by rewrite -hc.
have heq := mlkem_u_inv_good_lookup ss RO1E.FunRO.f{1}
  KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2} RF.RF.m{1} UU2.lD{2} m{1} hi hcorrect.
have hm : KEMROMx2.RO2.RO.m{1}.[m{1}] = None by smt().
rewrite -he hc.
exact (mlkem_u_inv_good_extend ss RO1E.FunRO.f{1}
  KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2} RF.RF.m{1} UU2.lD{2} m{1} kk hi hcorrect hm).
qed.

lemma mlkem_t_fresh_enc : equiv [TT.TT(RO.LRO).enc ~ TT.BasePKE.enc :
  ={arg} /\ m{1} \notin RO.RO.m{1} ==> ={res}].
proof.
(* COMPLETE THIS *)
  proc; inline *; auto.
  move=> &1 &2 [[hp hm] hf].
  split; first by move=> rR hrR.
  move=> _ r0L hr0L; rewrite hf /=.
  rewrite FMap.get_set_sameE.
  by rewrite /= hp hm.
qed.

lemma mlkem_u_sim_get2_good (ss : pkey * MLWE_PKE_Hash.skey) : equiv [
  H1.get2 ~ H2(RO1E.FunRO).get2 :
  ={arg, RO1E.FunRO.f} /\
  KEMROMx2.CCA.sk{1}.`1 = ss /\ KEMROMx2.CCA.sk{2}.`1 = ss /\
  !H1.bad{1} /\ !H1.bad{2} /\
  dec ss.`2 (enc (RO1E.FunRO.f{1} arg{1}) ss.`1 arg{1}) = Some arg{1} /\
  mlkem_u_inv ss RO1E.FunRO.f{1} KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2}
    RF.RF.m{1} UU2.lD{2}
  ==> ={res} /\ !H1.bad{1} /\ !H1.bad{2} /\
  mlkem_u_inv ss RO1E.FunRO.f{1} KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2}
    RF.RF.m{1} UU2.lD{2}].
proof.
(* COMPLETE THIS *)
  proc; inline *; wp; rnd; wp; skip.
  move=> &1 &2 [[hm hf] [hs1 [hs2 [hb1 [hb2 [hc hi]]]]]].
  rewrite -hm -hf hs1 hs2 hc /= hb1 hb2 /=.
  rewrite hc /=.
  move=> k hk.
  have [hgood hdec] := mlkem_u_good_enc ss RO1E.FunRO.f{1} m{1} hc.
  move: hi; rewrite /mlkem_u_inv; move=> [ha [hv hs]].
  have hac := ha (enc (RO1E.FunRO.f{1} m{1}) ss.`1 m{1}).
  rewrite hgood hdec /= in hac.
  rewrite hac -FMap.domE.
  case (m{1} \in KEMROMx2.RO2.RO.m{2}) => hr; first have hl : m{1} \in KEMROMx2.RO2.RO.m{1} by smt(FMap.domE).
  rewrite hl /=; smt().
  case (m{1} \in KEMROMx2.RO2.RO.m{1}) => hl /=.
  rewrite FMap.get_setE /=.
  split; first exact ha.
  split; first exact hv.
  move=> mm.
  rewrite FMap.domE !FMap.get_setE.
  case (mm = m{1}) => he /=; smt(FMap.get_some FMap.domE).
  rewrite !FMap.get_setE /=.
  split.
  move=> cc.
  rewrite List.assoc_cons FMap.get_setE.
  case (cc = enc (RO1E.FunRO.f{1} m{1}) ss.`1 m{1}) => he; first by rewrite he hgood hdec /=.
  have hneq : goodc cc ss RO1E.FunRO.f{1} => oc2m cc ss <> m{1} by smt(mlkem_u_cipher_eq).
  smt().
  split; move=> mm; rewrite FMap.domE !FMap.get_setE; case (mm = m{1}) => he /=; smt(FMap.domE).
qed.

module MlkemCorrIndex(QQ : TT.PKEROM.CORR_ADV) = {
  proc run() : plaintext list = {
    TT.Correctness_Adv1(RO.RO, QQ).main();
    return TT.CO1.queried;
  }
  proc main(ii : int) : bool = {
    var queries, mm;
    queries <@ run();
    mm <- nth witness queries ii;
    return 0 <= ii < size queries /\
      dec TT.CO1.sk (enc (oget RO.RO.m.[mm]) TT.CO1.pk mm) <> Some mm;
  }
  proc guess() : bool = {
    var queries, ii, mm;
    queries <@ run();
    ii <$ [0..TT.qHC];
    mm <- nth witness queries ii;
    return 0 <= ii < size queries /\
      dec TT.CO1.sk (enc (oget RO.RO.m.[mm]) TT.CO1.pk mm) <> Some mm;
  }
}.

lemma mlkem_bowl_choose_ll (QL <: TT.PKE.OWL_CPA_ADV) :
  islossless TT.PKE.OWvsIND.Bowl(QL).choose.
proof. by proc; rnd; rnd; auto; rewrite TT.dplaintext_ll. qed.

lemma mlkem_bowl_guess_ll (QL <: TT.PKE.OWL_CPA_ADV) :
  islossless QL.find => islossless TT.PKE.OWvsIND.Bowl(QL).guess.
proof. by move=> qll; proc; call qll; rnd; auto; rewrite DBool.dbool_ll. qed.

lemma mlkem_bl_ll (QW <: TT.PKE.OW_CPA_ADV) :
  islossless QW.find => islossless TT.PKE.OWvsIND.BL(QW).find.
proof. by move=> qll; proc; call qll; auto. qed.

lemma mlkem_bl_size (QW <: TT.PKE.OW_CPA_ADV) :
  hoare [TT.PKE.OWvsIND.BL(QW).find : true ==> size res <= 1].
proof. proc; call (_ : true); auto; progress; case result; auto. qed.

lemma mlkem_bowp_ll (QW <: TT.PKE.OW_CPA_ADV) :
  islossless TT.PKE.BOWp(TT.BasePKE, QW).find.
proof. by proc; rnd; auto; rewrite TT.dplaintext_ll. qed.

lemma mlkem_u_sim_get2_flag (ss : pkey * MLWE_PKE_Hash.skey) : equiv [
  H1.get2 ~ H2(RO1E.FunRO).get2 :
  ={arg, RO1E.FunRO.f, H1.bad} /\
  KEMROMx2.CCA.sk{1}.`1 = ss /\ KEMROMx2.CCA.sk{2}.`1 = ss
  ==> ={H1.bad}].
proof. by proc; inline *; auto; progress; smt(). qed.

lemma mlkem_u_get2_real_ll : islossless H1.get2.
proof. by proc; inline *; islossless; apply dkey_ll. qed.

lemma mlkem_u_get2_sim_ll : islossless H2(RO1E.FunRO).get2.
proof. by proc; inline *; islossless; apply dkey_ll. qed.

lemma mlkem_u_dec_real_ll : islossless UU1(RF.RF,H1).dec.
proof. by proc; inline *; islossless; apply dkey_ll. qed.

lemma mlkem_u_dec_sim_ll : islossless UU2(H2(RO1E.FunRO)).dec.
proof. by proc; inline *; islossless; apply dkey_ll. qed.

lemma mlkem_u_sim_get2 (ss : pkey * MLWE_PKE_Hash.skey) : equiv [
  H1.get2 ~ H2(RO1E.FunRO).get2 :
  ={arg, RO1E.FunRO.f, H1.bad} /\
  KEMROMx2.CCA.sk{1}.`1 = ss /\ KEMROMx2.CCA.sk{2}.`1 = ss /\
  (!H1.bad{1} =>
    mlkem_u_inv ss RO1E.FunRO.f{1} KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2}
      RF.RF.m{1} UU2.lD{2})
  ==> ={H1.bad} /\ (!H1.bad{1} => ={res} /\
    mlkem_u_inv ss RO1E.FunRO.f{1} KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2}
      RF.RF.m{1} UU2.lD{2})].
proof.
  proc*.
  case (H1.bad{1}).
  + inline *; auto; progress; smt().
  case (dec ss.`2 (enc (RO1E.FunRO.f{1} m{1}) ss.`1 m{1}) = Some m{1}).
  + call (mlkem_u_sim_get2_good ss); auto; progress; smt().
  inline *; auto; progress; smt().
qed.

lemma mlkem_u_real_bad : phoare [UU1(RF.RF,H1).dec : H1.bad ==> H1.bad] = 1%r.
proof.
  conseq mlkem_u_dec_real_ll (_ : H1.bad ==> H1.bad) => //.
  proc.
  seq 2 : H1.bad; first by inline *; auto.
  if.
  + inline *; sp; if; auto.
  inline *; auto; progress; smt().
qed.

section MlkemUCore.
declare module QU <: KEMROMx2.CCA_ADV{
  -KEMROMx2.CCA, -RO1E.FunRO, -KEMROMx2.RO1.RO, -KEMROMx2.RO2.RO,
  -RF.RF, -UU2, -H1, -H2, -Gm2, -Gm3, -H2BOWMod, -CountHx2}.

lemma mlkem_u_instrument : equiv [
  Gm1(RO_x2E, QU).main ~ Gm2(H1, UU1(RF.RF), QU).main2 :
  ={glob QU} ==> ={res}].
proof.
  proc; inline *; wp.
  call (_ : ={RO1E.FunRO.f, KEMROMx2.RO2.RO.m, RF.RF.m,
               KEMROMx2.CCA.sk, KEMROMx2.CCA.cstar}).
  + proc; inline *; sim.
  + proc; inline *; sim.
  + proc; inline *; sim.
  auto; progress; smt().
qed.
lemma mlkem_u_sim :
  (forall (HH <: KEMROMx2.POracle_x2{-QU}) (OO <: KEMROMx2.CCA_ORC{-QU}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless QU(HH,OO).guess) =>
  equiv [Gm2(H1, UU1(RF.RF), QU).main2 ~
    Gm2(H2(RO1E.FunRO), UU2, QU).main2 :
    ={glob QU} ==> ={H1.bad} /\ (!H1.bad{2} => ={res})].
proof.
  move=> qll; proc.
  call (_ : H1.bad,
    ={H1.bad, RO1E.FunRO.f, KEMROMx2.CCA.sk, KEMROMx2.CCA.cstar} /\
    mlkem_u_inv KEMROMx2.CCA.sk{1}.`1 RO1E.FunRO.f{1}
      KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2} RF.RF.m{1} UU2.lD{2},
    ={H1.bad}).
  + by move=> HH OO oll h1ll h2ll; exact (qll HH OO h1ll h2ll oll).
  + proc; sp; if.
    + by smt().
    + exlim KEMROMx2.CCA.sk{1}.`1 => ss.
      call (mlkem_u_sim_decap ss); auto; progress; smt().
    + by auto.
  + move=> &2 Hb.
    conseq (_ : H1.bad ==> H1.bad); first 2 by smt().
    proc; sp; if; last by auto.
    call mlkem_u_real_bad; auto.
  + move=> &1; proc; sp; if; last by auto.
    call mlkem_u_dec_sim_ll; auto.
  + by proc; auto; smt().
  + by move=> &2 Hb; proc; auto.
  + by move=> &1; proc; auto.
  + proc*; exlim KEMROMx2.CCA.sk{1}.`1 => ss.
    call (mlkem_u_sim_get2 ss); auto; progress; smt().
  + move=> &2 Hb; proc; wp; rnd; wp; skip; smt(dkey_ll).
  + move=> &1; proc; inline RO1E.FunRO.get; wp; rnd; wp; skip; smt(dkey_ll).
  seq 8 8 : (={glob QU, pk, RO1E.FunRO.f, KEMROMx2.CCA.sk, KEMROMx2.CCA.cstar, H1.bad} /\
    !H1.bad{1} /\ mlkem_u_inv KEMROMx2.CCA.sk{1}.`1 RO1E.FunRO.f{1}
      KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2} RF.RF.m{1} UU2.lD{2}).
  + inline *; auto; rewrite /mlkem_u_inv; progress;
      smt(List.assoc_nil FMap.emptyE FMap.mem_empty).
  exlim KEMROMx2.CCA.sk{1}.`1 => ss.
  inline UU2(H1).enc UU2(H2(RO1E.FunRO)).enc.
  wp; call (mlkem_u_sim_get2 ss).
  inline *; auto; progress; smt().
qed.
lemma mlkem_u_smooth_sim :
  (forall (HH <: KEMROMx2.POracle_x2{-QU}) (OO <: KEMROMx2.CCA_ORC{-QU}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless QU(HH,OO).guess) =>
  equiv [Gm2(H1,UU1(RF.RF),QU).main2 ~ Gm2(H2(RO1E.FunRO),UU2,QU).main :
    ={glob QU} ==> ={H1.bad} /\ (!H1.bad{2} => ={res})].
proof.
  move=> qll; proc*.
  inline Gm2(H2(RO1E.FunRO),UU2,QU).main.
  wp; rnd{2}; call (mlkem_u_sim qll); auto; progress; smt(DBool.dbool_ll).
qed.

lemma mlkem_u_smooth_gap &m :
  (forall (HH <: KEMROMx2.POracle_x2{-QU}) (OO <: KEMROMx2.CCA_ORC{-QU}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless QU(HH,OO).guess) =>
  `|Pr[Gm2(H1,UU1(RF.RF),QU).main2() @ &m : res] -
    Pr[Gm2(H2(RO1E.FunRO),UU2,QU).main() @ &m : res]| <=
    Pr[Gm2(H2(RO1E.FunRO),UU2,QU).main() @ &m : H1.bad].
proof.
  move=> qll.
  have hg : Pr[Gm2(H1,UU1(RF.RF),QU).main2() @ &m : res /\ !H1.bad] =
    Pr[Gm2(H2(RO1E.FunRO),UU2,QU).main() @ &m : res /\ !H1.bad].
  + byequiv (mlkem_u_smooth_sim qll) => //; smt().
  have hb : Pr[Gm2(H1,UU1(RF.RF),QU).main2() @ &m : H1.bad] =
    Pr[Gm2(H2(RO1E.FunRO),UU2,QU).main() @ &m : H1.bad].
  + byequiv (mlkem_u_smooth_sim qll) => //.
  have hl : Pr[Gm2(H1,UU1(RF.RF),QU).main2() @ &m : res /\ H1.bad] <=
    Pr[Gm2(H1,UU1(RF.RF),QU).main2() @ &m : H1.bad] by rewrite Pr[mu_sub].
  have hr : Pr[Gm2(H2(RO1E.FunRO),UU2,QU).main() @ &m : res /\ H1.bad] <=
    Pr[Gm2(H2(RO1E.FunRO),UU2,QU).main() @ &m : H1.bad] by rewrite Pr[mu_sub].
  have hzl : 0%r <= Pr[Gm2(H1,UU1(RF.RF),QU).main2() @ &m : res /\ H1.bad]
    by rewrite Pr[mu_ge0].
  have hzr : 0%r <= Pr[Gm2(H2(RO1E.FunRO),UU2,QU).main() @ &m : res /\ H1.bad]
    by rewrite Pr[mu_ge0].
  have hdl : Pr[Gm2(H1,UU1(RF.RF),QU).main2() @ &m : res] =
    Pr[Gm2(H1,UU1(RF.RF),QU).main2() @ &m : res /\ H1.bad] +
    Pr[Gm2(H1,UU1(RF.RF),QU).main2() @ &m : res /\ !H1.bad]
    by rewrite Pr[mu_split H1.bad].
  have hdr : Pr[Gm2(H2(RO1E.FunRO),UU2,QU).main() @ &m : res] =
    Pr[Gm2(H2(RO1E.FunRO),UU2,QU).main() @ &m : res /\ H1.bad] +
    Pr[Gm2(H2(RO1E.FunRO),UU2,QU).main() @ &m : res /\ !H1.bad]
    by rewrite Pr[mu_split H1.bad].
  smt().
qed.

end section MlkemUCore.

lemma mlkem_b1x2_count_inv
    (HH <: KEMROMx2.POracle_x2{-A, -CountH, -CountHx2})
    (OO <: KEMROM.CCA_ORC{-A, -CountH, -CountHx2}) :
  hoare [B1x2(A, CountHx2(HH), OO).guess :
    CountHx2.c_ht <= 0 /\ CountHx2.c_hu <= 0 ==>
    CountHx2.c_ht <= CountH.c_h /\ CountHx2.c_hu <= CountH.c_h].
proof.
  proc.
  call (_ : CountHx2.c_ht <= CountH.c_h /\ CountHx2.c_hu <= CountH.c_h);
    last by inline *; auto.
  + by proc*; call (_ : true); auto.
  proc; wp.
  call (_ : CountHx2.c_ht <= CountH.c_h /\ CountHx2.c_hu <= CountH.c_h ==>
    CountHx2.c_ht <= CountH.c_h + 1 /\ CountHx2.c_hu <= CountH.c_h + 1).
  + proc.
    seq 1 : (CountHx2.c_ht <= CountH.c_h /\ CountHx2.c_hu <= CountH.c_h);
      first by inline *; auto.
    if.
    + inline CountHx2; wp; call (_ : true); wp; call (_ : true); auto; progress; smt().
    auto; progress; smt().
  auto.
qed.

lemma mlkem_b1x2_budget
    (HH <: KEMROMx2.POracle_x2{-A, -CountH, -CountHx2})
    (OO <: KEMROM.CCA_ORC{-A, -CountH, -CountHx2}) :
  (forall (HR <: KEMROM.POracle{-CountH, -A}) (OD <: KEMROM.CCA_ORC{-CountH, -A}),
    hoare [A(CountH(HR),OD).guess : CountH.c_h = 0 ==> CountH.c_h <= qHK]) =>
  hoare [B1x2(A, CountHx2(HH), OO).guess : true ==> CountH.c_h <= qHK].
proof.
  move=> hq; proc.
  call (hq (<: B1x2(A,CountHx2(HH),OO).BH) OO).
  inline *; auto.
qed.

lemma mlkem_b1x2_counts
    (HH <: KEMROMx2.POracle_x2{-A, -CountH, -CountHx2})
    (OO <: KEMROM.CCA_ORC{-A, -CountH, -CountHx2}) :
  (forall (HR <: KEMROM.POracle{-CountH, -A}) (OD <: KEMROM.CCA_ORC{-CountH, -A}),
    hoare [A(CountH(HR),OD).guess : CountH.c_h = 0 ==> CountH.c_h <= qHK]) =>
  hoare [B1x2(A, CountHx2(HH), OO).guess :
    CountHx2.c_ht = 0 /\ CountHx2.c_hu = 0 ==>
    CountHx2.c_ht <= qHK /\ CountHx2.c_hu <= qHK].
proof.
  move=> hq.
  by conseq (mlkem_b1x2_count_inv HH OO) (mlkem_b1x2_budget HH OO hq) => />; smt().
qed.

op mlkem_u_challenge_cache (tt : plaintext) (cc : ciphertext)
    (ml mr : (plaintext,key) fmap) (ll lr : (ciphertext * key) list) =
  (forall xx, xx <> tt => ml.[xx] = mr.[xx]) /\
  (forall dd, dd <> cc => assoc ll dd = assoc lr dd).

lemma mlkem_u_challenge_get (ss : pkey * MLWE_PKE_Hash.skey)
    (tt : plaintext) (cc : ciphertext) : equiv [
  H2(RO1E.FunRO).get2 ~ H2(RO1E.FunRO).get2 :
    ={arg, RO1E.FunRO.f, H1.bad, H2.invert} /\
    KEMROMx2.CCA.sk{1}.`1 = ss /\ KEMROMx2.CCA.sk{2}.`1 = ss /\
    KEMROMx2.CCA.cstar{1} = Some cc /\ KEMROMx2.CCA.cstar{2} = Some cc /\
    H2.mtgt{1} = tt /\ H2.mtgt{2} = tt /\ (!H1.bad{1} => dec ss.`2 cc = Some tt) /\
    mlkem_u_challenge_cache tt cc KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2}
      UU2.lD{1} UU2.lD{2}
    ==> ={H1.bad, H2.invert} /\ H2.mtgt{1} = tt /\ H2.mtgt{2} = tt /\
    (!H2.invert{2} => ={res} /\
      mlkem_u_challenge_cache tt cc KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2}
        UU2.lD{1} UU2.lD{2})].
proof.
(* COMPLETE THIS *)
  proc; inline *; auto.
  rewrite /mlkem_u_challenge_cache.
  move=> &1 &2 [[hm [hf [hb hi]]] [hsk1 [hsk2 [hc1 [hc2 [ht1 [ht2 [hdec [hmap hlist]]]]]]]]].
  rewrite hm hf hb hi hsk1 hsk2 hc1 hc2 ht1 ht2 /=.
  case (dec ss.`2 (enc (RO1E.FunRO.f{2} m{2}) ss.`1 m{2}) = Some m{2} => H1.bad{2}) => hbad /=; first smt().
  case (! (!(m{2} = tt && dec ss.`2 cc = Some tt) => H2.invert{2})) => hni /=; last smt().
  have hneq : m{2} <> tt by smt().
  have hdc : dec ss.`2 cc = Some tt by smt().
  have hcneq : enc (RO1E.FunRO.f{2} m{2}) ss.`1 m{2} <> cc.
  case (enc (RO1E.FunRO.f{2} m{2}) ss.`1 m{2} = cc) => heq //; move: hbad; rewrite heq hdc /=; smt().
  have hmget := hmap m{2} hneq.
  have hlget := hlist (enc (RO1E.FunRO.f{2} m{2}) ss.`1 m{2}) hcneq.
  have hdom : (m{2} \in KEMROMx2.RO2.RO.m{1}) = (m{2} \in KEMROMx2.RO2.RO.m{2}) by smt(FMap.domE).
  rewrite hdom hlget /=.
  move=> kL hkL; case (m{2} \notin KEMROMx2.RO2.RO.m{2}) => hmem /=; last smt().
  case (assoc UU2.lD{2} (enc (RO1E.FunRO.f{2} m{2}) ss.`1 m{2}) <> None<:key>) => hassoc /=.
  rewrite !FMap.get_setE /=.
  split; last exact hlist.
  move=> xx hxx; rewrite !FMap.get_setE (hmap xx hxx).
  reflexivity.
  rewrite !FMap.get_setE /=; split.
  + move=> xx hxx; rewrite !FMap.get_setE (hmap xx hxx); reflexivity.
  + move=> dd hdd; rewrite !List.assoc_cons (hlist dd hdd); reflexivity.
qed.

lemma mlkem_u_challenge_dec (cc : ciphertext) : equiv [
  UU2(H2(RO1E.FunRO)).dec ~ UU2(H2(RO1E.FunRO)).dec :
    ={arg} /\ arg{1}.`2 <> cc /\
    (forall dd, dd <> cc => assoc UU2.lD{1} dd = assoc UU2.lD{2} dd)
    ==> ={res} /\
    (forall dd, dd <> cc => assoc UU2.lD{1} dd = assoc UU2.lD{2} dd)].
proof.
  proc; sp; if.
  + by smt().
  + by auto; progress; smt().
  auto; progress; smt(List.assoc_cons).
qed.

module type MlkemHashOW(HH : TT.PKEROM.POracle) = {
  proc find(pk : pkey, cc : ciphertext) : plaintext option
}.

module MlkemNoVA = {
  proc pco(mm : plaintext, cc : ciphertext) : bool = { return false; }
  proc cvo(cc : ciphertext) : bool = { return false; }
}.

module MlkemHashOWU(QQ : KEMROMx2.CCA_ADV, HH : TT.PKEROM.POracle) = {
  proc find = BUUOWMod(QQ, HH, MlkemNoVA).find
}.

module MlkemTOracle = {
  proc get(xx : plaintext) : randomness = {
    var rr;
    TT.CO1.bad <- TT.CO1.bad || xx = TT.Gm.m;
    rr <@ RO.RO.get(xx);
    return rr;
  }
}.

module MlkemTGame(QH : MlkemHashOW) = {
  proc main(programmed : bool) : bool = {
    var rr, mo;
    (TT.CO1.pk,TT.CO1.sk) <$ TT.kg;
    TT.Gm.m <$ TT.dplaintext;
    rr <$ drand;
    TT.PKEROM.OW_PCVA.cc <- enc rr TT.CO1.pk TT.Gm.m;
    RO.RO.init();
    TT.CO1.bad <- false;
    if (programmed) RO.RO.m.[TT.Gm.m] <- rr;
    mo <@ QH(MlkemTOracle).find(TT.CO1.pk,TT.PKEROM.OW_PCVA.cc);
    return mo <> None /\ dec TT.CO1.sk TT.PKEROM.OW_PCVA.cc = mo;
  }
}.

op mlkem_t_eq (mc : plaintext) (mm1 mm2 : (plaintext, randomness) fmap) =
  forall xx, xx <> mc => mm1.[xx] = mm2.[xx].

lemma mlkem_t_get_coupling : equiv [
  MlkemTOracle.get ~ MlkemTOracle.get :
  ={arg, TT.Gm.m, TT.CO1.bad} /\
  mlkem_t_eq TT.Gm.m{1} RO.RO.m{1} RO.RO.m{2}
  ==> ={TT.CO1.bad} /\
  (!TT.CO1.bad{2} => ={res, TT.Gm.m} /\
    mlkem_t_eq TT.Gm.m{1} RO.RO.m{1} RO.RO.m{2})].
proof.
  proc; inline *; wp; rnd; wp; skip.
  rewrite /mlkem_t_eq; progress; smt(FMap.get_setE FMap.domE).
qed.

section MlkemTCore.
declare module QH <: MlkemHashOW{-RO.RO, -RO.FRO, -TT.CO1, -TT.Gm, -TT.PKEROM.OW_PCVA}.

lemma mlkem_t_upto :
  (forall (HH <: TT.PKEROM.POracle{-QH}),
    islossless HH.get => islossless QH(HH).find) =>
  equiv [MlkemTGame(QH).main ~ MlkemTGame(QH).main :
    ={glob QH} /\ programmed{1} /\ !programmed{2}
    ==> ={TT.CO1.bad} /\ (!TT.CO1.bad{2} => ={res})].
proof.
  move=> qll; proc.
  call (_ : TT.CO1.bad,
    ={TT.CO1.bad, TT.Gm.m, TT.CO1.pk, TT.CO1.sk, TT.PKEROM.OW_PCVA.cc} /\
    mlkem_t_eq TT.Gm.m{1} RO.RO.m{1} RO.RO.m{2},
    ={TT.CO1.bad}).
  + by proc*; call mlkem_t_get_coupling; auto; progress; smt().
  + move=> &m2 hb; proc; inline *; auto; progress; rewrite ?drand_ll; smt().
  + move=> &m1; proc; inline *; auto; progress; rewrite ?drand_ll; smt().
  inline RO.RO.init.
  rcondt{1} 7; first by auto.
  rcondf{2} 7; first by auto.
  auto; rewrite /mlkem_t_eq; progress; smt(FMap.get_setE FMap.emptyE).
qed.

lemma mlkem_t_program_bound &m :
  (forall (HH <: TT.PKEROM.POracle{-QH}),
    islossless HH.get => islossless QH(HH).find) =>
  Pr[MlkemTGame(QH).main(true) @ &m : res] <=
  Pr[MlkemTGame(QH).main(false) @ &m : res] +
  Pr[MlkemTGame(QH).main(false) @ &m : TT.CO1.bad].
proof.
  move=> qll.
  have hg : Pr[MlkemTGame(QH).main(true) @ &m : res /\ !TT.CO1.bad] =
    Pr[MlkemTGame(QH).main(false) @ &m : res /\ !TT.CO1.bad].
  + byequiv (mlkem_t_upto qll) => //; smt().
  have hb : Pr[MlkemTGame(QH).main(true) @ &m : TT.CO1.bad] =
    Pr[MlkemTGame(QH).main(false) @ &m : TT.CO1.bad].
  + byequiv (mlkem_t_upto qll) => //.
  have hs : Pr[MlkemTGame(QH).main(true) @ &m : res /\ TT.CO1.bad] <=
    Pr[MlkemTGame(QH).main(true) @ &m : TT.CO1.bad].
  + by rewrite Pr[mu_sub].
  have hr : Pr[MlkemTGame(QH).main(false) @ &m : res /\ !TT.CO1.bad] <=
    Pr[MlkemTGame(QH).main(false) @ &m : res].
  + by rewrite Pr[mu_sub].
  rewrite Pr[mu_split TT.CO1.bad]; smt().
qed.
end section MlkemTCore.

op mlkem_co_domain (ii : int) (qs : plaintext list) (mm : (plaintext, randomness) fmap) =
  uniq qs /\ forall xx, xx \in mm <=> xx \in qs /\ List.index xx qs <> ii.

op mlkem_co_pick (ii : int) (qs : plaintext list) =
  if 0 <= ii < size qs then nth witness qs ii
  else head witness (filter (fun xx => !(xx \in qs)) TT.FinT.enum).

lemma mlkem_co_domain_empty ii : mlkem_co_domain ii [] empty.
proof. by rewrite /mlkem_co_domain /=; smt(FMap.mem_empty). qed.

lemma mlkem_co_lazy_get : hoare [TT.CO1(RO.LRO).get :
  mlkem_co_domain TT.CO1.i TT.CO1.queried RO.RO.m
  ==> mlkem_co_domain TT.CO1.i TT.CO1.queried RO.RO.m].
proof.
(* COMPLETE THIS *)
  proc; inline *; sp; if.
  + if.
  + auto; rewrite /mlkem_co_domain.
  move=> &hr [[[Hy [Hu Hd]] Hfresh] Hi]; split.
  by rewrite cats1 rcons_uniq Hfresh Hu.
  move=> xx; rewrite Hd mem_cat /= index_cat; case (xx \in TT.CO1.queried{hr})=> Hmem /=.
  trivial.
  case (xx = x{hr})=> Hxx /=.
  by rewrite Hxx index_head /= Hi.
  trivial.
  rcondt 3; first by auto; rewrite /mlkem_co_domain; smt().
  auto; rewrite /mlkem_co_domain.
  move=> &hr [[[Hy [Hu Hd]] Hfresh] Hi] r1 Hr /=; split; first by rewrite cats1 rcons_uniq Hfresh Hu.
  move=> xx; rewrite FMap.mem_set Hd mem_cat /= index_cat; case (xx = x{hr})=> Hxx.
  by rewrite Hxx Hfresh /= index_head /= Hi.
  by case (xx \in TT.CO1.queried{hr})=> Hmem /=.
  if.
  rcondf 3; first by auto; rewrite /mlkem_co_domain /index; smt().
  by auto.
  by auto.
qed.

lemma mlkem_co_pick_fresh ii qs mm :
  mlkem_co_domain ii qs mm => size qs < TT.FinT.card =>
  mlkem_co_pick ii qs \notin mm.
proof.
  rewrite /mlkem_co_domain /mlkem_co_pick; move=> [hu hd] hs.
  case (0 <= ii < size qs) => hi.
  + have hx := List.index_uniq witness ii qs hi hu.
    have hh := hd (nth witness qs ii); smt().
  have hzero : filter (fun xx => !(xx \in qs)) TT.FinT.enum = [] => false.
  + move=> he.
    have hin : mem TT.FinT.enum <= mem qs.
    + move=> xx hx.
      have hz : !(xx \in filter (fun yy => !(yy \in qs)) TT.FinT.enum) by rewrite he.
      move: hz; rewrite List.mem_filter hx /=; smt().
    have hh := List.uniq_leq_size TT.FinT.enum qs TT.FinT.enum_uniq hin.
    move: hs; rewrite /TT.FinT.card; smt().
  have hn : filter (fun xx => !(xx \in qs)) TT.FinT.enum <> [] by smt().
  have hh := List.mem_head_behead witness
    (filter (fun xx => !(xx \in qs)) TT.FinT.enum) hn
    (head witness (filter (fun xx => !(xx \in qs)) TT.FinT.enum)).
  have hx := hd (head witness (filter (fun xx => !(xx \in qs)) TT.FinT.enum)).
  smt(List.mem_filter).
qed.

module MlkemCorrMainD(QQ : TT.PKEROM.CORR_ADV, OO : RO.RO) = {
  proc distinguish = TT.B(QQ, OO).main
}.

module MlkemCorrBaseD(QQ : TT.PKEROM.CORR_ADV, OO : RO.RO) = {
  proc distinguish = TT.PKE.Correctness_Adv(TT.BasePKE, TT.B(QQ, OO)).main
}.

section MlkemCorrDerandomization.
declare module QQC <: TT.PKEROM.CORR_ADV{-TT.CO1, -RO.RO, -RO.FRO}.

lemma mlkem_corr_main_lazy &m :
  Pr[TT.B(QQC, RO.RO).main() @ &m : res] =
  Pr[TT.B(QQC, RO.LRO).main() @ &m : res].
proof.
  byequiv (RO.FullEager.RO_LRO_D (MlkemCorrMainD(QQC)) _) => //.
  by move=> xx; apply drand_ll.
qed.

lemma mlkem_corr_base_lazy &m :
  Pr[TT.PKE.Correctness_Adv(TT.BasePKE, TT.B(QQC, RO.RO)).main() @ &m : res] =
  Pr[TT.PKE.Correctness_Adv(TT.BasePKE, TT.B(QQC, RO.LRO)).main() @ &m : res].
proof.
  byequiv (RO.FullEager.RO_LRO_D (MlkemCorrBaseD(QQC)) _) => //.
  by move=> xx; apply drand_ll.
qed.

lemma mlkem_co_lazy_find_domain : hoare [TT.B(QQC, RO.LRO).find : true ==>
  mlkem_co_domain TT.CO1.i TT.CO1.queried RO.RO.m /\
  res = mlkem_co_pick TT.CO1.i TT.CO1.queried].
proof.
  proc.
  conseq (_ : true ==> mlkem_co_domain TT.CO1.i TT.CO1.queried RO.RO.m).
  call mlkem_co_lazy_get.
  inline TT.Correctness_Adv1(RO.LRO,QQC).main'.
  wp.
  call (_ : mlkem_co_domain TT.CO1.i TT.CO1.queried RO.RO.m).
  + exact mlkem_co_lazy_get.
  inline *.
  auto.
  progress.
  by rewrite FMap.mem_empty in H0.
qed.

lemma mlkem_co_lazy_find_fresh :
  TT.qHC < TT.FinT.card - 1 =>
  hoare [TT.B(QQC, RO.LRO).find : true ==> size TT.CO1.queried <= TT.qHC + 1] =>
  hoare [TT.B(QQC, RO.LRO).find : true ==> res \notin RO.RO.m].
proof.
  move=> hc hsz.
  conseq mlkem_co_lazy_find_domain hsz => //.
  progress; smt(mlkem_co_pick_fresh).
qed.
end section MlkemCorrDerandomization.


module MlkemHashPCVA(QH : MlkemHashOW, HH : TT.PKEROM.POracle,
                     OO : TT.PKEROM.VA_ORC) = {
  proc find = QH(HH).find
}.

lemma mlkem_tt_dec_sound (HH <: TT.PKEROM.POracle)
    (ss : pkey * MLWE_PKE_Hash.skey) (cc : ciphertext) :
  hoare [TT.TT(HH).dec : arg = (ss,cc) ==>
    res = None \/ res = dec ss.`2 cc].
proof.
  proc; sp; if; last by auto.
  wp.
  call (_ : true); auto; progress; smt().
qed.

section MlkemTBridges.
declare module QHT <: MlkemHashOW{
  -RO.RO, -RO.FRO, -TT.CO1, -TT.Gm, -TT.PKEROM.OW_PCVA,
  -TT.PKE.OW_CPA, -TT.PKE.OWL_CPA, -TT.O_AdvOW, -TT.CountO}.

lemma mlkem_t_validation : equiv [
  TT.PKEROM.OW_PCVA(RO.RO, TT.TT, MlkemHashPCVA(QHT)).main ~
  MlkemTGame(QHT).main : ={glob QHT} /\ programmed{2}
  ==> res{1} => res{2}].
proof.
  proc.
  seq 5 8 : (m'{1} = mo{2} /\
    TT.PKEROM.OW_PCVA.sk{1}.`2 = TT.CO1.sk{2} /\
    TT.PKEROM.OW_PCVA.cc{1} = TT.PKEROM.OW_PCVA.cc{2}).
  + call (_ : ={RO.RO.m}).
    + by proc; inline *; auto; progress; smt().
    inline *.
    rcondt{2} ^if; first by auto.
    rcondt{1} ^if; first by auto; smt(FMap.mem_empty).
    auto; progress; smt(FMap.get_set_sameE).
  inline *; sp; if{1}.
  + wp; rnd{1}; wp; skip; progress; rewrite ?drand_ll; smt(some_oget).
  auto; progress; smt().
qed.
end section MlkemTBridges.

section MlkemCorrKeys.
declare module QCK <: TT.PKEROM.CORR_ADV{-TT.CO1, -RO.RO, -RO.FRO}.

lemma mlkem_co_lazy_find_keys pp ss :
  hoare [TT.B(QCK, RO.LRO).find : arg = (pp,ss) ==>
    TT.CO1.pk = pp /\ TT.CO1.sk = ss].
proof.
  proc; call (_ : true).
  + by inline *; auto.
  inline TT.Correctness_Adv1(RO.LRO,QCK).main'; wp.
  call (_ : true).
  + by proc; inline *; auto.
  inline *; auto.
qed.

lemma mlkem_co_lazy_find_refl : equiv [
  TT.B(QCK, RO.LRO).find ~ TT.B(QCK, RO.LRO).find :
  ={arg, glob QCK} ==> ={res, RO.RO.m, TT.CO1.pk, TT.CO1.sk}].
proof. by proc; inline *; sim. qed.

lemma mlkem_co_lazy_find_couple pp ss :
  TT.qHC < TT.FinT.card - 1 =>
  hoare [TT.B(QCK, RO.LRO).find : true ==> size TT.CO1.queried <= TT.qHC + 1] =>
  equiv [TT.B(QCK, RO.LRO).find ~ TT.B(QCK, RO.LRO).find :
    ={glob QCK} /\ arg{1} = (pp,ss) /\ arg{2} = (pp,ss)
    ==> ={res, RO.RO.m} /\ TT.CO1.pk{1} = pp /\ TT.CO1.sk{1} = ss /\
      res{1} \notin RO.RO.m{1}].
proof.
  move=> hc hsz.
  by conseq mlkem_co_lazy_find_refl (mlkem_co_lazy_find_keys pp ss)
    (mlkem_co_lazy_find_fresh QCK hc hsz) => />; smt().
qed.

lemma mlkem_corr_lazy_base :
  TT.qHC < TT.FinT.card - 1 =>
  hoare [TT.B(QCK, RO.LRO).find : true ==> size TT.CO1.queried <= TT.qHC + 1] =>
  equiv [TT.B(QCK, RO.LRO).main ~
    TT.PKE.Correctness_Adv(TT.BasePKE, TT.B(QCK, RO.LRO)).main :
    ={glob QCK} ==> ={res}].
proof.
  move=> hc hsz; proc.
  seq 1 1 : (={glob QCK} /\ TT.CO1.pk{1} = pk{2} /\ TT.CO1.sk{1} = sk{2}).
  + by inline *; auto; progress; smt().
  exlim TT.CO1.pk{1} => pp.
  exlim TT.CO1.sk{1} => ss.
  seq 1 1 : (m{1} = m{2} /\ TT.CO1.pk{1} = pp /\ TT.CO1.sk{1} = ss /\
    pk{2} = pp /\ sk{2} = ss /\ m{1} \notin RO.RO.m{1}).
  + call (mlkem_co_lazy_find_couple pp ss hc hsz); auto; progress; smt().
  inline *; auto.
  move=> &1 &2 [hm [hp1 [hs1 [hp2 [hs2 hf]]]]].
  split; first by move=> rr hr.
  move=> _ rr hr; rewrite hf /=.
  rewrite FMap.get_set_sameE.
  by rewrite /= hm hp1 hs1 hp2 hs2.
qed.
end section MlkemCorrKeys.

type mlkem_corr_trace = (pkey * MLWE_PKE_Hash.skey) *
  (plaintext, randomness) fmap * plaintext list.

op mlkem_corr_bad_at (tt : mlkem_corr_trace) (mm : plaintext) =
  dec tt.`1.`2 (enc (oget tt.`2.[mm]) tt.`1.`1 mm) <> Some mm.

op mlkem_corr_bad_trace (tt : mlkem_corr_trace) =
  has (mlkem_corr_bad_at tt) tt.`3.

op mlkem_corr_bad_index (tt : mlkem_corr_trace) =
  List.find (mlkem_corr_bad_at tt) tt.`3.

module MlkemCorrTrace(QQ : TT.PKEROM.CORR_ADV) = {
  proc main() : mlkem_corr_trace = {
    TT.Correctness_Adv1(RO.RO, QQ).main();
    return ((TT.CO1.pk, TT.CO1.sk), RO.RO.m, TT.CO1.queried);
  }
}.

clone PlugAndPray as MlkemCorrGuess with
  type tval <- int,
  op indices <- iota_ 0 (TT.qHC + 1),
  type tin <- unit,
  type tres <- mlkem_corr_trace
  proof indices_not_nil by
    (rewrite -List.size_eq0 List.Iota.size_iota; smt(TT.ge0_qHC)).

lemma mlkem_corr_guess_index (tt : mlkem_corr_trace) :
  mlkem_corr_bad_trace tt /\ size tt.`3 <= TT.qHC + 1 =>
  mlkem_corr_bad_index tt \in iota_ 0 (TT.qHC + 1).
proof.
  rewrite /mlkem_corr_bad_trace /mlkem_corr_bad_index List.has_find List.Iota.mem_iota.
  smt(List.find_ge0).
qed.

lemma mlkem_corr_guess_factor (QQ <: TT.PKEROM.CORR_ADV) &m :
  Pr[MlkemCorrTrace(QQ).main() @ &m :
    mlkem_corr_bad_trace res /\ size res.`3 <= TT.qHC + 1] =
  (TT.qHC + 1)%r *
  Pr[MlkemCorrGuess.Guess(MlkemCorrTrace(QQ)).main() @ &m :
    (mlkem_corr_bad_trace res.`2 /\ size res.`2.`3 <= TT.qHC + 1) /\
    res.`1 = mlkem_corr_bad_index res.`2].
proof.
  have hh := MlkemCorrGuess.PBound_mult (MlkemCorrTrace(QQ))
    (fun _ tt => mlkem_corr_bad_trace tt /\ size tt.`3 <= TT.qHC + 1)
    (fun _ tt => mlkem_corr_bad_index tt) () &m _.
  + by move=> gg tt; apply mlkem_corr_guess_index.
  move: hh; rewrite List.undup_id ?List.Iota.iota_uniq List.Iota.size_iota.
  smt(TT.ge0_qHC).
qed.

lemma mlkem_co_count_real nn : hoare [TT.CO1(RO.RO).get :
  TT.CO1.counter = nn ==> TT.CO1.counter = nn + 1].
proof. by proc; sp; if; if; inline *; auto; progress; smt(). qed.

lemma mlkem_co_count_lazy nn : hoare [TT.CO1(RO.LRO).get :
  TT.CO1.counter = nn ==> TT.CO1.counter = nn + 1].
proof. by proc; sp; if; if; inline *; auto; progress; smt(). qed.

lemma mlkem_co_count_bound_real nn : hoare [TT.CO1(RO.RO).get :
  TT.CO1.counter <= nn ==> TT.CO1.counter <= nn + 1].
proof. by proc; sp; if; if; inline *; auto; progress; smt(). qed.

lemma mlkem_co_count_bound_lazy nn : hoare [TT.CO1(RO.LRO).get :
  TT.CO1.counter <= nn ==> TT.CO1.counter <= nn + 1].
proof. by proc; sp; if; if; inline *; auto; progress; smt(). qed.

lemma mlkem_co_list_bound (qs : plaintext list) (xx : plaintext) (nn : int) :
  size qs <= nn => size (qs ++ [xx]) <= nn + 1.
proof. by rewrite List.size_cat /=; smt(). qed.

lemma mlkem_co_size_real : hoare [TT.CO1(RO.RO).get :
  size TT.CO1.queried <= TT.CO1.counter ==> size TT.CO1.queried <= TT.CO1.counter].
proof.
  proc; sp; if; if; inline *; auto.
  + move=> &hr [[[_ hsz] _] _] rr _.
    rewrite List.size_cat /=; smt().
  + move=> &hr [[[_ hsz] _] _] rr _.
    rewrite List.size_cat /=; smt().
  + move=> &hr [[[_ hsz] _] _] rr _; smt().
  move=> &hr [[[_ hsz] _] _]; smt().
qed.

lemma mlkem_co_size_lazy : hoare [TT.CO1(RO.LRO).get :
  size TT.CO1.queried <= TT.CO1.counter ==> size TT.CO1.queried <= TT.CO1.counter].
proof.
  proc; sp; if; if; inline *; auto.
  + move=> &hr [[[_ hsz] _] _].
    rewrite List.size_cat /=; smt().
  + move=> &hr [[[_ hsz] _] _] rr _.
    rewrite List.size_cat /=; smt().
  + move=> &hr [[[_ hsz] _] _] rr _; smt().
  move=> &hr [[[_ hsz] _] _]; smt().
qed.

section MlkemQueryAccounting.
declare module QCNT <: TT.PKEROM.CORR_ADV{-TT.CO1, -RO.RO, -RO.FRO}.

lemma mlkem_co_find_size_real : hoare [TT.B(QCNT, RO.RO).find : true ==>
  size TT.CO1.queried <= TT.CO1.counter].
proof.
  proc; call mlkem_co_size_real.
  inline TT.Correctness_Adv1(RO.RO,QCNT).main'; wp.
  call (_ : size TT.CO1.queried <= TT.CO1.counter).
  + exact mlkem_co_size_real.
  inline *; auto.
qed.

lemma mlkem_co_find_size_lazy : hoare [TT.B(QCNT, RO.LRO).find : true ==>
  size TT.CO1.queried <= TT.CO1.counter].
proof.
  proc; call mlkem_co_size_lazy.
  inline TT.Correctness_Adv1(RO.LRO,QCNT).main'; wp.
  call (_ : size TT.CO1.queried <= TT.CO1.counter).
  + exact mlkem_co_size_lazy.
  inline *; auto.
qed.

lemma mlkem_co_find_count_real qb :
  hoare [QCNT(TT.CO1(RO.RO)).find : TT.CO1.counter = 0 ==> TT.CO1.counter <= qb] =>
  hoare [TT.B(QCNT, RO.RO).find : true ==> TT.CO1.counter <= qb + 1].
proof.
  move=> hq; proc; call (mlkem_co_count_bound_real qb).
  inline TT.Correctness_Adv1(RO.RO,QCNT).main'; wp; call hq.
  inline *; auto.
qed.

lemma mlkem_co_find_count_lazy qb :
  hoare [QCNT(TT.CO1(RO.LRO)).find : TT.CO1.counter = 0 ==> TT.CO1.counter <= qb] =>
  hoare [TT.B(QCNT, RO.LRO).find : true ==> TT.CO1.counter <= qb + 1].
proof.
  move=> hq; proc; call (mlkem_co_count_bound_lazy qb).
  inline TT.Correctness_Adv1(RO.LRO,QCNT).main'; wp; call hq.
  inline *; auto.
qed.

lemma mlkem_co_find_bound_real qb :
  hoare [QCNT(TT.CO1(RO.RO)).find : TT.CO1.counter = 0 ==> TT.CO1.counter <= qb] =>
  hoare [TT.B(QCNT, RO.RO).find : true ==> size TT.CO1.queried <= qb + 1].
proof.
  move=> hq.
  by conseq mlkem_co_find_size_real (mlkem_co_find_count_real qb hq) => />; smt().
qed.

lemma mlkem_co_find_bound_lazy qb :
  hoare [QCNT(TT.CO1(RO.LRO)).find : TT.CO1.counter = 0 ==> TT.CO1.counter <= qb] =>
  hoare [TT.B(QCNT, RO.LRO).find : true ==> size TT.CO1.queried <= qb + 1].
proof.
  move=> hq.
  by conseq mlkem_co_find_size_lazy (mlkem_co_find_count_lazy qb hq) => />; smt().
qed.
end section MlkemQueryAccounting.

section MlkemTBaseGames.
declare module QTA <: MlkemHashOW{
  -RO.RO, -RO.FRO, -TT.CO1, -TT.Gm, -TT.PKEROM.OW_PCVA,
  -TT.PKE.OW_CPA, -TT.PKE.OWL_CPA, -TT.O_AdvOW, -TT.CountO}.

lemma mlkem_t_base_ow &m :
  Pr[MlkemTGame(QTA).main(false) @ &m : res] =
  Pr[TT.PKE.OW_CPA(TT.BasePKE, TT.AdvOW(MlkemHashPCVA(QTA))).main() @ &m : res].
proof.
  byequiv (_ : ={glob QTA} /\ !programmed{1} ==> ={res}) => //.
  proc; inline *; wp.
  call (_ : ={RO.RO.m}).
  + by proc; inline *; auto; progress; smt().
  auto; progress; smt(some_oget).
qed.

lemma mlkem_t_domain_membership (mm : plaintext) (mp : (plaintext, randomness) fmap) :
  mm \in FSet.elems (fdom mp) <=> mm \in mp.
proof. by rewrite -FSet.memE FMap.mem_fdom. qed.

lemma mlkem_t_base_query &m :
  0 < TT.qH + TT.qP =>
  Pr[MlkemTGame(QTA).main(false) @ &m : TT.CO1.bad] =
  Pr[TT.PKE.OWL_CPA(TT.BasePKE, TT.AdvOWL_query(MlkemHashPCVA(QTA))).main() @ &m : res].
proof.
  move=> hq.
  have hil : is_lossless (DInterval.dinter 0 (TT.qH + TT.qP - 1)).
  + apply DInterval.dinter_ll; smt().
  byequiv (_ : ={glob QTA} /\ !programmed{1} ==> TT.CO1.bad{1} = res{2}) => //.
  proc; inline *; wp; rnd{2}.
  call (_ : ={RO.RO.m} /\ TT.Gm.m{1} = TT.PKE.OWL_CPA.m{2} /\
    (TT.CO1.bad{1} <=> TT.Gm.m{1} \in RO.RO.m{1})).
  + by proc; inline *; auto; progress; smt(FMap.domE FMap.get_setE FMap.mem_set).
  auto; progress;
    smt(FMap.mem_empty mlkem_t_domain_membership).
qed.
end section MlkemTBaseGames.
module MlkemCoActual(O : RO.RO) = {
  proc get(xx : plaintext) : randomness = {
    var rr;
    rr <@ O.get(xx);
    if (!(xx \in TT.CO1.queried))
      TT.CO1.queried <- TT.CO1.queried ++ [xx];
    TT.CO1.counter <- TT.CO1.counter + 1;
    return rr;
  }
}.

module MlkemCoReal(O : RO.RO) = {
  proc get(xx : plaintext) : randomness = {
    var rr;
    rr <@ O.get(xx);
    if (!(xx \in TT.CO1.queried)) {
      TT.CO1.bad <- TT.CO1.bad || size TT.CO1.queried = TT.CO1.i;
      TT.CO1.queried <- TT.CO1.queried ++ [xx];
    }
    TT.CO1.counter <- TT.CO1.counter + 1;
    return rr;
  }
}.

module type MlkemCorrDriver(HH : TT.PKEROM.POracle) = {
  proc run(pp : pkey, ss : MLWE_PKE_Hash.skey) : unit
}.

module MlkemCorrDrive(QQ : TT.PKEROM.CORR_ADV, HH : TT.PKEROM.POracle) = {
  proc run(pp : pkey, ss : MLWE_PKE_Hash.skey) : unit = {
    var mm;
    mm <@ QQ(HH).find(pp,(pp,ss));
    HH.get(mm);
  }
}.

module MlkemCorrSelected(QD : MlkemCorrDriver, HH : TT.PKEROM.POracle) = {
  proc main() : bool = {
    var mm;
    (TT.CO1.pk, TT.CO1.sk) <@ TT.BasePKE.kg();
    TT.CO1.i <$ [0..TT.qHC];
    RO.RO.init();
    TT.CO1.queried <- [];
    TT.CO1.counter <- 0;
    TT.CO1.bad <- false;
    QD(HH).run(TT.CO1.pk, TT.CO1.sk);
    mm <- nth witness TT.CO1.queried TT.CO1.i;
    return 0 <= TT.CO1.i < size TT.CO1.queried /\
      dec TT.CO1.sk (enc (oget RO.RO.m.[mm]) TT.CO1.pk mm) <> Some mm;
  }
}.

op mlkem_co_selected (ii : int) (qs : plaintext list)
    (fm : (plaintext, randomness) fmap) (mm : plaintext) (rr : randomness) =
  0 <= ii < size qs /\ nth witness qs ii = mm /\ fm.[mm] = Some rr.

lemma mlkem_co_selected_append ii qs (fm : (plaintext, randomness) fmap) mm rr xx :
  mlkem_co_selected ii qs fm mm rr =>
  mlkem_co_selected ii (qs ++ [xx]) fm mm rr.
proof.
  rewrite /mlkem_co_selected List.size_cat List.nth_cat /=; smt(List.size_ge0).
qed.

lemma mlkem_co_selected_set ii qs (fm : (plaintext, randomness) fmap) mm rr xx vv :
  mlkem_co_selected ii qs fm mm rr => xx \notin fm =>
  mlkem_co_selected ii qs fm.[xx <- vv] mm rr.
proof.
  rewrite /mlkem_co_selected FMap.get_setE FMap.domE; smt().
qed.

lemma mlkem_co_real_selected mm rr : hoare [MlkemCoReal(RO.RO).get :
  mlkem_co_selected TT.CO1.i TT.CO1.queried RO.RO.m mm rr ==>
  mlkem_co_selected TT.CO1.i TT.CO1.queried RO.RO.m mm rr].
proof.
  proc; inline *; auto; progress;
    smt(mlkem_co_selected_append mlkem_co_selected_set).
qed.

lemma mlkem_co_fake_selected mm rr : hoare [TT.CO1(RO.RO).get :
  mlkem_co_selected TT.CO1.i TT.CO1.queried RO.RO.m mm rr ==>
  mlkem_co_selected TT.CO1.i TT.CO1.queried RO.RO.m mm rr].
proof.
  proc; sp; if; if; inline *; auto; progress;
    smt(mlkem_co_selected_append mlkem_co_selected_set).
qed.

lemma mlkem_co_real_ll : islossless MlkemCoReal(RO.RO).get.
proof. by proc; inline *; islossless; apply drand_ll. qed.

lemma mlkem_co_fake_ll : islossless TT.CO1(RO.RO).get.
proof. by proc; inline *; islossless; apply drand_ll. qed.
section MlkemUFairProbability.
declare module QFP <: KEMROMx2.CCA_ADV{
  -KEMROMx2.CCA, -RO1E.FunRO, -KEMROMx2.RO1.RO, -KEMROMx2.RO2.RO,
  -RF.RF, -UU2, -H1, -H2, -Gm2, -Gm3, -H2BOWMod, -CountHx2}.

lemma mlkem_u_zero_half &m :
  islossless QFP(H2(RO1E.FunRO), KEMROMx2.CCA(H2(RO1E.FunRO),UU2,QFP).O).guess =>
  Pr[Gm3(H2(RO1E.FunRO),UU2,QFP).main_0adv() @ &m : res] = 1%r/2%r.
proof.
  move=> qll; byphoare (_ : true ==> res) => //.
  proc.
  seq 17 : true 1%r (1%r/2%r) 0%r 0%r => //.
  + inline *; islossless;
      smt(dkey_ll drand_ll TT.kg_ll TT.dplaintext_ll RO1E.MUniFinFun.dfun_ll).
  case H1.bad.
  + conseq (_ : H1.bad ==> H1.bad /\ nobias) => />.
    kill 2; first by islossless.
    rnd (pred1 true); skip; progress; smt(DBool.dbool1E).
  conseq (_ : !H1.bad ==> !H1.bad /\ b' = b) => />.
  kill 1; first by islossless.
  rnd (pred1 b'); skip; progress; smt(DBool.dbool1E).
qed.

lemma mlkem_u_fair_half &m :
  islossless QFP(H2(RO1E.FunRO), KEMROMx2.CCA(H2(RO1E.FunRO),UU2,QFP).O).guess =>
  Pr[Gm3(H2(RO1E.FunRO),UU2,QFP).main() @ &m : res] = 1%r/2%r.
proof.
  move=> qll.
  have -> : Pr[Gm3(H2(RO1E.FunRO),UU2,QFP).main() @ &m : res] =
    Pr[Gm3(H2(RO1E.FunRO),UU2,QFP).main_0adv() @ &m : res].
  + byequiv (mlkem_u_fair_keys QFP) => //.
  exact (mlkem_u_zero_half &m qll).
qed.
end section MlkemUFairProbability.

lemma mlkem_u_sticky_flags (aa bb : bool) : phoare [H2(RO1E.FunRO).get2 :
  (H1.bad /\ aa) \/ (H2.invert /\ bb) ==>
  (H1.bad /\ aa) \/ (H2.invert /\ bb)] = 1%r.
proof.
  conseq mlkem_u_get2_sim_ll
    (_ : (H1.bad /\ aa) \/ (H2.invert /\ bb) ==>
         (H1.bad /\ aa) \/ (H2.invert /\ bb)) => //.
  proc; inline *; auto; progress; smt().
qed.

section MlkemUChallenge.
declare module QUC <: KEMROMx2.CCA_ADV{
  -KEMROMx2.CCA, -RO1E.FunRO, -KEMROMx2.RO1.RO, -KEMROMx2.RO2.RO,
  -RF.RF, -UU2, -H1, -H2, -Gm2, -Gm3, -H2BOWMod, -CountHx2}.

lemma mlkem_u_challenge_game :
  (forall (HH <: KEMROMx2.POracle_x2{-QUC}) (OO <: KEMROMx2.CCA_ORC{-QUC}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless QUC(HH,OO).guess) =>
  equiv [Gm2(H2(RO1E.FunRO),UU2,QUC).main ~ Gm3(H2(RO1E.FunRO),UU2,QUC).main :
    ={glob QUC} ==> !H2.invert{2} => ={res}].
proof.
  move=> qll; proc.
  inline Gm2(H2(RO1E.FunRO),UU2,QUC).main2.
  wp; rnd; wp.
  call (_ : H1.bad \/ H2.invert,
    ={H1.bad, H2.invert, RO1E.FunRO.f, KEMROMx2.CCA.sk,
      KEMROMx2.CCA.cstar, H2.mtgt} /\
    KEMROMx2.CCA.cstar{1} <> None /\
    dec KEMROMx2.CCA.sk{1}.`1.`2 (oget KEMROMx2.CCA.cstar{1}) = Some H2.mtgt{1} /\
    mlkem_u_challenge_cache H2.mtgt{1} (oget KEMROMx2.CCA.cstar{1})
      KEMROMx2.RO2.RO.m{1} KEMROMx2.RO2.RO.m{2} UU2.lD{1} UU2.lD{2},
    (H1.bad{1} /\ H1.bad{2}) \/ (H2.invert{1} /\ H2.invert{2})).
  + by move=> HH OO oll h1ll h2ll; exact (qll HH OO h1ll h2ll oll).
  + proc; sp; if.
    + by smt().
    + exlim (oget KEMROMx2.CCA.cstar{1}) => cc.
      call (mlkem_u_challenge_dec cc); auto;
        rewrite /mlkem_u_challenge_cache; progress; smt(some_oget).
    by auto; smt().
  + move=> &2 hb; proc; sp; if; last by auto.
    call mlkem_u_dec_sim_ll; auto; progress; smt().
  + move=> &1; proc; sp; if; last by auto.
    call mlkem_u_dec_sim_ll; auto; progress; smt().
  + by proc; auto; smt().
  + by move=> &2 hb; proc; auto.
  + by move=> &1; proc; auto.
  + proc*.
    exlim KEMROMx2.CCA.sk{1}.`1 => ss.
    exlim H2.mtgt{1} => tt.
    exlim (oget KEMROMx2.CCA.cstar{1}) => cc.
    call (mlkem_u_challenge_get ss tt cc); auto; progress; smt(some_oget).
  + move=> &2 hb.
    conseq (mlkem_u_sticky_flags H1.bad{2} H2.invert{2}) => />; smt().
  + move=> &1.
    conseq (mlkem_u_sticky_flags H1.bad{1} H2.invert{1}) => />; smt().
  swap{2} 10 8.
  inline *; auto.
  rewrite /mlkem_u_challenge_cache /= ?FMap.mem_empty ?List.assoc_nil.
  move=> &1 &2 hg ff hf.
  split; first exact hf.
  move=> _ ss hs.
  split; first exact hs.
  move=> _ kk hk bb hb mm hm kk2 hk2.
  rewrite FMap.mem_empty List.assoc_nil /=.
  split.
  + case (dec ss.`2 (enc (ff mm) ss.`1 mm) <> Some mm) => hbad; first by smt().
    have hdec : dec ss.`2 (enc (ff mm) ss.`1 mm) = Some mm by smt().
    rewrite hdec /= FMap.get_set_sameE /= hg /=.
    split.
    + move=> xx hx; rewrite FMap.get_setE; smt().
    move=> dd hd; rewrite !List.assoc_cons !List.assoc_nil; smt().
  move=> _ rl rr gl bl il tl ldl ml gr br ir tr ldr mr hp nb hnb hni.
  move: hp; rewrite hni /=.
  case br => hbr /=.
  + by move=> hbl; rewrite hbl.
  by move=> [heq [_ [[hbl _] _]]]; rewrite hbl heq.
qed.
end section MlkemUChallenge.

op mlkem_co_before (ii : int) (qs : plaintext list)
    (fm : (plaintext,randomness) fmap) =
  0 <= ii /\ size qs <= ii /\ uniq qs /\
  (forall xx, xx \in qs <=> xx \in fm).

op mlkem_co_pair (ii : int) (ql qr : plaintext list)
    (fl fr : (plaintext,randomness) fmap) =
  exists mm rr, mlkem_co_selected ii ql fl mm rr /\
                mlkem_co_selected ii qr fr mm rr.

lemma mlkem_co_selection_get : equiv [
  MlkemCoReal(RO.RO).get ~ TT.CO1(RO.RO).get :
    ={arg, TT.CO1.i, TT.CO1.queried, RO.RO.m, TT.CO1.bad} /\
    !TT.CO1.bad{2} /\ mlkem_co_before TT.CO1.i{2} TT.CO1.queried{2} RO.RO.m{2}
    ==> ={TT.CO1.bad} /\
    (TT.CO1.bad{2} => mlkem_co_pair TT.CO1.i{2}
      TT.CO1.queried{1} TT.CO1.queried{2} RO.RO.m{1} RO.RO.m{2}) /\
    (!TT.CO1.bad{2} => ={res, TT.CO1.queried, RO.RO.m} /\
      mlkem_co_before TT.CO1.i{2} TT.CO1.queried{2} RO.RO.m{2})].
proof.
  proc; inline *; sp; if{2}.
  + if{2}.
    + auto.
      move=> &1 &2 [[hpre hn] hi].
      case: hpre => hy [hx [heq [hnb hbfr]]].
      case: heq => harg [hieq [hqs [hmap hb]]].
      have hmf : x{2} \notin RO.RO.m{2}.
      + move: hbfr; rewrite /mlkem_co_before; smt().
      rewrite hx harg hieq hqs hmap hb hnb hn hmf /=.
      move=> rr hrr; split; first by rewrite hi.
      rewrite /mlkem_co_pair; exists x{2} rr; split;
        rewrite /mlkem_co_selected -hi List.size_cat List.nth_cat FMap.get_set_sameE /=;
        smt(List.size_ge0).
    auto.
    move=> &1 &2 [[hpre hn] hi].
    case: hpre => hy [hx [heq [hnb hbfr]]].
    case: heq => harg [hieq [hqs [hmap hb]]].
    have hmf : x{2} \notin RO.RO.m{2}.
    + move: hbfr; rewrite /mlkem_co_before; smt().
    rewrite hx harg hieq hqs hmap hb hnb hn hmf hi /=.
    move=> rr hrr.
    case: hbfr => hni [hs [hu hd]].
    rewrite /mlkem_co_before List.size_cat List.cat_uniq /= hu hn /=.
    split; first exact hni.
    split; first by smt().
    move=> yy; rewrite List.mem_cat FMap.mem_set /=.
    have hh := hd yy; smt().
  rcondt{2} 1.
  + auto; rewrite /mlkem_co_before; progress; smt(List.has_find List.has_pred1).
  auto; rewrite /mlkem_co_before /mlkem_co_pair /mlkem_co_selected;
    progress; smt(FMap.domE).
qed.

module MlkemUWiden(QQ : KEMROMx2.CCA_ADV) = {
  proc main() : bool = {
    H2BOWMod.crd <- 0;
    H2BOWMod.mf <- None;
    Gm3(H2BOWMod(RO1E.FunRO),UU2,QQ).main();
    return H2BOWMod.crd = 1 /\ H2BOWMod.mf = Some H2.mtgt /\
      dec KEMROMx2.CCA.sk.`1.`2 (oget KEMROMx2.CCA.cstar) = Some H2.mtgt;
  }
}.

op mlkem_u_record_inv (tt : plaintext) (mp : (plaintext,key) fmap)
    (iv : bool) (nn : int) (mf : plaintext option) =
  (iv <=> tt \in mp) /\ nn = b2i (tt \in mp) /\
  (tt \in mp => mf = Some tt).

lemma mlkem_u_record_cipher (ss : pkey * MLWE_PKE_Hash.skey)
    (ff : plaintext -> randomness) (tt mm : plaintext) (cc : ciphertext) :
  cc = enc (ff tt) ss.`1 tt => dec ss.`2 cc = Some tt =>
  dec ss.`2 (enc (ff mm) ss.`1 mm) = Some mm =>
  (enc (ff mm) ss.`1 mm = cc <=> mm = tt).
proof. smt(). qed.


lemma mlkem_u_record_fresh (tt : plaintext) (mp : (plaintext,key) fmap)
    (iv : bool) (nn : int) (mf : plaintext option) (xx : plaintext) (kk : key) :
  mlkem_u_record_inv tt mp iv nn mf => xx \notin mp =>
  mlkem_u_record_inv tt mp.[xx <- kk]
    (xx <> tt => iv) (nn + b2i (xx = tt))
    (if xx = tt then Some xx else mf).
proof.
  rewrite /mlkem_u_record_inv FMap.mem_set /b2i.
  smt(FMap.domE).
qed.

lemma mlkem_u_record_repeat (tt : plaintext) (mp : (plaintext,key) fmap)
    (iv : bool) (nn : int) (mf : plaintext option) (xx : plaintext) :
  mlkem_u_record_inv tt mp iv nn mf => !(xx \notin mp) =>
  mlkem_u_record_inv tt mp (xx <> tt => iv) nn mf.
proof. rewrite /mlkem_u_record_inv; smt(FMap.domE). qed.

lemma mlkem_u_wide_get (ss : pkey * MLWE_PKE_Hash.skey)
    (tt : plaintext) (cc : ciphertext) : equiv [
  H2(RO1E.FunRO).get2 ~ H2BOWMod(RO1E.FunRO).get2 :
    ={arg, RO1E.FunRO.f, H1.bad, KEMROMx2.RO2.RO.m, UU2.lD} /\ !H1.bad{1} /\
    KEMROMx2.CCA.sk{1}.`1 = ss /\ KEMROMx2.CCA.sk{2}.`1 = ss /\
    KEMROMx2.CCA.cstar{1} = Some cc /\ KEMROMx2.CCA.cstar{2} = Some cc /\
    H2.mtgt{1} = tt /\ H2.mtgt{2} = tt /\
    cc = enc (RO1E.FunRO.f{1} tt) ss.`1 tt /\ dec ss.`2 cc = Some tt /\
    mlkem_u_record_inv tt KEMROMx2.RO2.RO.m{2} H2.invert{1}
      H2BOWMod.crd{2} H2BOWMod.mf{2}
    ==> ={H1.bad} /\ H2.mtgt{1} = tt /\ (!H1.bad{2} => ={res, KEMROMx2.RO2.RO.m, UU2.lD} /\
      mlkem_u_record_inv tt KEMROMx2.RO2.RO.m{2} H2.invert{1}
        H2BOWMod.crd{2} H2BOWMod.mf{2})].
proof.
  proc; inline *; auto.
  move=> &1 &2 [[hm [hf [hb [hmap hld]]]] [hnb [hs1 [hs2 [hc1 [hc2 [ht1 [ht2 [hcc [hdec hinv]]]]]]]]]].
  rewrite hb in hnb; rewrite hf in hcc.
  rewrite hm hf hb hmap hld hs1 hs2 hc1 hc2 ht1 hnb /=.
  move=> kk hk.
  case (dec ss.`2 (enc (RO1E.FunRO.f{2} m{2}) ss.`1 m{2}) <> Some m{2}) => hfail;
    first by smt().
  have hgood : dec ss.`2 (enc (RO1E.FunRO.f{2} m{2}) ss.`1 m{2}) = Some m{2} by smt().
  have hce := mlkem_u_record_cipher ss RO1E.FunRO.f{2} tt m{2} cc hcc hdec hgood.
  rewrite hgood /= hce.
  rewrite hdec /=.
  case (m{2} \notin KEMROMx2.RO2.RO.m{2}) => hnew.
  + case (assoc UU2.lD{2} (enc (RO1E.FunRO.f{2} m{2}) ss.`1 m{2}) <> None<:key>) => hassoc;
      rewrite ?hnew ?hassoc /=; apply mlkem_u_record_fresh; assumption.
  rewrite ?hnew /=; apply mlkem_u_record_repeat; assumption.
qed.

lemma mlkem_co_negative_get : equiv [RO.RO.get ~ TT.CO1(RO.RO).get :
  ={arg, RO.RO.m} /\ TT.CO1.i{2} = -1 ==> ={res, RO.RO.m} /\ TT.CO1.i{2} = -1].
proof.
  proc; sp; if{2}.
  + rcondf{2} ^if; first by auto; smt(List.size_ge0).
    by inline *; auto.
  rcondt{2} ^if; first by auto; smt(List.find_ge0).
  by inline *; auto.
qed.

lemma mlkem_co_negative_member (mm : plaintext) : hoare [TT.CO1(RO.RO).get :
  arg = mm /\ TT.CO1.i = -1 ==> mm \in TT.CO1.queried /\ RO.RO.m.[mm] <> None].
proof.
  proc; sp; if.
  + rcondf ^if; first by auto; smt(List.size_ge0).
    inline *; auto; progress; smt(FMap.get_set_sameE FMap.domE List.mem_cat).
  rcondt ^if; first by auto; smt(List.find_ge0).
  inline *; auto; progress; smt(FMap.get_set_sameE FMap.domE).
qed.

module MlkemCorrMarked(QQ : TT.PKEROM.CORR_ADV) = {
  proc main() : mlkem_corr_trace * plaintext = {
    var mm;
    (TT.CO1.pk, TT.CO1.sk) <@ TT.BasePKE.kg();
    mm <@ TT.Correctness_Adv1(RO.RO,QQ).main'(TT.CO1.pk,TT.CO1.sk,-1);
    TT.CO1(RO.RO).get(mm);
    return (((TT.CO1.pk,TT.CO1.sk),RO.RO.m,TT.CO1.queried),mm);
  }
}.

section MlkemCorrTraceEntry.
declare module QCE <: TT.PKEROM.CORR_ADV{-RO.RO, -RO.FRO, -TT.CO1}.

lemma mlkem_corr_marked_trace : equiv [
  MlkemCorrMarked(QCE).main ~ MlkemCorrTrace(QCE).main :
  ={glob QCE} ==> res{1}.`1 = res{2}].
proof.
  proc; inline *; wp.
  conseq (_ : ={glob QCE} ==> ={TT.CO1.pk,TT.CO1.sk,RO.RO.m,TT.CO1.queried}) => />.
  sim.
qed.

lemma mlkem_corr_marked_member : hoare [MlkemCorrMarked(QCE).main :
  true ==> res.`2 \in res.`1.`3].
proof.
  proc; seq 2 : (TT.CO1.i = -1).
  + inline TT.Correctness_Adv1(RO.RO,QCE).main'; wp.
    call (_ : TT.CO1.i = -1).
    + by proc; sp; if; if; inline *; auto.
    inline *; auto.
  exlim mm => mm0.
  call (mlkem_co_negative_member mm0); auto.
qed.

lemma mlkem_corr_marked_bound &m :
  Pr[MlkemCorrMarked(QCE).main() @ &m : mlkem_corr_bad_at res.`1 res.`2] <=
  Pr[MlkemCorrTrace(QCE).main() @ &m : mlkem_corr_bad_trace res].
proof.
  byequiv (_ : ={glob QCE} ==> mlkem_corr_bad_at res{1}.`1 res{1}.`2 =>
    mlkem_corr_bad_trace res{2}) => //.
  conseq mlkem_corr_marked_trace mlkem_corr_marked_member => />.
  rewrite /mlkem_corr_bad_trace; smt(List.hasP).
qed.
end section MlkemCorrTraceEntry.
op mlkem_u_bad_witness (ss : pkey * MLWE_PKE_Hash.skey)
    (ff : plaintext -> randomness) (bad : bool) (me : plaintext option) =
  (bad <=> me <> None) /\
  (me <> None => dec ss.`2 (enc (ff (oget me)) ss.`1 (oget me)) <> Some (oget me)).

lemma mlkem_u_witness_get (ss : pkey * MLWE_PKE_Hash.skey) :
  hoare [H2(RO1E.FunRO).get2 :
    KEMROMx2.CCA.sk.`1 = ss /\
    mlkem_u_bad_witness ss RO1E.FunRO.f H1.bad H2.merr ==>
    mlkem_u_bad_witness ss RO1E.FunRO.f H1.bad H2.merr].
proof.
  proc; inline RO1E.FunRO.get; auto; rewrite /mlkem_u_bad_witness;
    progress; smt(some_oget).
qed.

section MlkemUCorrectnessWitness.
declare module QUM <: KEMROMx2.CCA_ADV{
  -KEMROMx2.CCA, -RO1E.FunRO, -KEMROMx2.RO1.RO, -KEMROMx2.RO2.RO,
  -RF.RF, -UU2, -H1, -H2, -Gm2, -Gm3, -H2BOWMod, -CountHx2}.

lemma mlkem_uc_witness (ss : pkey * MLWE_PKE_Hash.skey) :
  hoare [BUUC(QUM,RO1E.FunRO).find : arg = (ss.`1,ss) ==>
    res = oget H2.merr /\ mlkem_u_bad_witness ss RO1E.FunRO.f H1.bad H2.merr].
proof.
  proc.
  call (_ : KEMROMx2.CCA.sk.`1 = ss /\
    mlkem_u_bad_witness ss RO1E.FunRO.f H1.bad H2.merr).
  + proc; sp; if; last by auto.
    inline *; sp; if; auto.
  + by proc; inline *; auto.
  + proc; inline CountHx2; wp; call (mlkem_u_witness_get ss); auto.
  inline *; auto; rewrite /mlkem_u_bad_witness; progress; smt(some_oget).
qed.

lemma mlkem_uci_witness (ss : pkey * MLWE_PKE_Hash.skey) :
  hoare [BUUCI(QUM,RO1E.FunRO).find : arg = (ss.`1,ss) ==>
    res = oget H2.merr /\ mlkem_u_bad_witness ss RO1E.FunRO.f H1.bad H2.merr].
proof.
  proc.
  call (_ : KEMROMx2.CCA.sk.`1 = ss /\
    mlkem_u_bad_witness ss RO1E.FunRO.f H1.bad H2.merr).
  + proc; sp; if; last by auto.
    inline *; sp; if; auto.
  + by proc; inline *; auto.
  + proc; inline CountHx2; wp; call (mlkem_u_witness_get ss); auto.
  inline *; auto; rewrite /mlkem_u_bad_witness; progress; smt(some_oget).
qed.
end section MlkemUCorrectnessWitness.

section MlkemUBadGames.
declare module QBG <: KEMROMx2.CCA_ADV{
  -KEMROMx2.CCA, -RO1E.FunRO, -KEMROMx2.RO1.RO, -KEMROMx2.RO2.RO,
  -RF.RF, -UU2, -H1, -H2, -Gm2, -Gm3, -H2BOWMod, -CountHx2}.

lemma mlkem_uc_corr_sound :
  hoare [TT.PKEROM.Correctness_Adv(RO1E.FunRO,TT.TT,BUUC(QBG)).main :
    true ==> H1.bad => res].
proof.
  proc; seq 2 : (pk = sk.`1); first by inline *; auto.
  exlim sk => ss.
  inline TT.TT RO1E.FunRO.get.
  wp; call (mlkem_uc_witness QBG ss); auto;
    rewrite /mlkem_u_bad_witness; progress; smt().
qed.

lemma mlkem_uci_corr_sound :
  hoare [TT.PKEROM.Correctness_Adv(RO1E.FunRO,TT.TT,BUUCI(QBG)).main :
    true ==> H1.bad => res].
proof.
  proc; seq 2 : (pk = sk.`1); first by inline *; auto.
  exlim sk => ss.
  inline TT.TT RO1E.FunRO.get.
  wp; call (mlkem_uci_witness QBG ss); auto;
    rewrite /mlkem_u_bad_witness; progress; smt().
qed.

lemma mlkem_uc_bad_game : equiv [
  Gm2(H2(RO1E.FunRO),UU2,QBG).main ~
  TT.PKEROM.Correctness_Adv(RO1E.FunRO,TT.TT,BUUC(QBG)).main :
    ={glob QBG} ==> ={H1.bad}].
proof.
  proc; inline *; wp; rnd{1}; wp.
  call (_ : ={RO1E.FunRO.f, KEMROMx2.RO2.RO.m, KEMROMx2.CCA.sk,
    KEMROMx2.CCA.cstar, H1.bad, H2.merr, H2.invert, H2.mtgt, UU2.lD}).
  + by proc; inline *; sim.
  + by proc; inline *; auto.
  + by proc; inline *; auto; progress; smt().
  auto; progress; smt(DBool.dbool_ll).
qed.

lemma mlkem_uci_bad_game : equiv [
  Gm3(H2(RO1E.FunRO),UU2,QBG).main ~
  TT.PKEROM.Correctness_Adv(RO1E.FunRO,TT.TT,BUUCI(QBG)).main :
    ={glob QBG} ==> ={H1.bad}].
proof.
  proc; inline *; wp; rnd{1}; wp.
  call (_ : ={RO1E.FunRO.f, KEMROMx2.RO2.RO.m, KEMROMx2.CCA.sk,
    KEMROMx2.CCA.cstar, H1.bad, H2.merr, H2.invert, H2.mtgt, UU2.lD}).
  + by proc; inline *; sim.
  + by proc; inline *; auto.
  + by proc; inline *; auto; progress; smt().
  auto; progress; smt(DBool.dbool_ll).
qed.

lemma mlkem_uc_bad_bound &m :
  Pr[Gm2(H2(RO1E.FunRO),UU2,QBG).main() @ &m : H1.bad] <=
  Pr[TT.PKEROM.Correctness_Adv(RO1E.FunRO,TT.TT,BUUC(QBG)).main() @ &m : res].
proof.
  byequiv (_ : ={glob QBG} ==> H1.bad{1} => res{2}) => //.
  conseq mlkem_uc_bad_game (_ : true ==> true) (_ : true ==> H1.bad => res) => //.
  exact mlkem_uc_corr_sound.
qed.

lemma mlkem_uci_bad_bound &m :
  Pr[Gm3(H2(RO1E.FunRO),UU2,QBG).main() @ &m : H1.bad] <=
  Pr[TT.PKEROM.Correctness_Adv(RO1E.FunRO,TT.TT,BUUCI(QBG)).main() @ &m : res].
proof.
  byequiv (_ : ={glob QBG} ==> H1.bad{1} => res{2}) => //.
  conseq mlkem_uci_bad_game (_ : true ==> true) (_ : true ==> H1.bad => res) => //.
  exact mlkem_uci_corr_sound.
qed.
end section MlkemUBadGames.

module MlkemCorrEager(QQ : TT.PKEROM.CORR_ADV, G : KEMROMx2.RO1.RO) = {
  module H = {
    proc init() = {}
    proc get = G.get
  }
  proc distinguish = TT.PKEROM.Correctness_Adv(H,TT.TT,QQ).main
}.

section MlkemCorrOracleChange.
declare module QEC <: TT.PKEROM.CORR_ADV{
  -RO1E.FunRO, -KEMROMx2.RO1.RO, -KEMROMx2.RO1.FRO, -RO.RO, -RO.FRO}.

lemma mlkem_corr_eager &m :
  Pr[TT.PKEROM.Correctness_Adv(KEMROMx2.RO1.RO,TT.TT,QEC).main() @ &m : res] =
  Pr[TT.PKEROM.Correctness_Adv(RO1E.FunRO,TT.TT,QEC).main() @ &m : res].
proof.
  have hll : forall (x : plaintext), is_lossless drand by move=> x; apply drand_ll.
  have h1 := RO1E.pr_RO_FinRO_D hll (MlkemCorrEager(QEC)) &m () (fun b => b).
  have h2 := RO1E.pr_FinRO_FunRO_D hll (MlkemCorrEager(QEC)) &m () (fun b => b).
  have hl : Pr[TT.PKEROM.Correctness_Adv(KEMROMx2.RO1.RO,TT.TT,QEC).main() @ &m : res] =
    Pr[KEMROMx2.RO1.MainD(MlkemCorrEager(QEC),KEMROMx2.RO1.RO).distinguish() @ &m : res].
  + byequiv (_ : ={glob QEC} ==> ={res}) => //.
    proc; inline *.
    wp -1 -2.
    conseq (_ : ={glob QEC} ==> ={m,rv}) => />.
    sim; auto; progress; smt().
  have hr : Pr[TT.PKEROM.Correctness_Adv(RO1E.FunRO,TT.TT,QEC).main() @ &m : res] =
    Pr[KEMROMx2.RO1.MainD(MlkemCorrEager(QEC),RO1E.FunRO).distinguish() @ &m : res].
  + byequiv (_ : ={glob QEC} ==> ={res}) => //.
    proc; inline *.
    wp -1 -2.
    conseq (_ : ={glob QEC} ==> ={m,rv}) => />.
    sim; auto; progress; smt().
  smt().
qed.

lemma mlkem_corr_ro_rename : equiv [
  TT.PKEROM.Correctness_Adv(KEMROMx2.RO1.RO,TT.TT,QEC).main ~
  TT.PKEROM.Correctness_Adv(RO.RO,TT.TT,QEC).main :
    ={glob QEC} ==> ={res}].
proof.
  proc.
  seq 3 3 : (={pk,sk,m} /\ KEMROMx2.RO1.RO.m{1} = RO.RO.m{2}).
  + call (_ : KEMROMx2.RO1.RO.m{1} = RO.RO.m{2}).
    + by proc; inline *; auto.
    inline *; auto.
  inline *.
  conseq (_ : ={pk,sk,m} /\ KEMROMx2.RO1.RO.m{1} = RO.RO.m{2}
    ==> ={m,m'}) => />.
  sim (: KEMROMx2.RO1.RO.m{1} = RO.RO.m{2}); auto; progress; smt().
qed.

lemma mlkem_corr_fun_ro &m :
  Pr[TT.PKEROM.Correctness_Adv(RO1E.FunRO,TT.TT,QEC).main() @ &m : res] =
  Pr[TT.PKEROM.Correctness_Adv(RO.RO,TT.TT,QEC).main() @ &m : res].
proof.
  rewrite -(mlkem_corr_eager &m).
  byequiv mlkem_corr_ro_rename => //.
qed.
end section MlkemCorrOracleChange.

lemma mlkem_co_pair_fixed ii ql qr fl fr :
  mlkem_co_pair ii ql qr fl fr <=>
  mlkem_co_selected ii ql fl (nth witness qr ii) (oget fr.[nth witness qr ii]) /\
  mlkem_co_selected ii qr fr (nth witness qr ii) (oget fr.[nth witness qr ii]).
proof.
  rewrite /mlkem_co_pair /mlkem_co_selected; smt(some_oget).
qed.

lemma mlkem_co_real_after mm rr : phoare [MlkemCoReal(RO.RO).get :
  TT.CO1.bad /\ mlkem_co_selected TT.CO1.i TT.CO1.queried RO.RO.m mm rr ==>
  TT.CO1.bad /\ mlkem_co_selected TT.CO1.i TT.CO1.queried RO.RO.m mm rr] = 1%r.
proof.
  conseq mlkem_co_real_ll
    (_ : TT.CO1.bad /\ mlkem_co_selected TT.CO1.i TT.CO1.queried RO.RO.m mm rr ==>
         TT.CO1.bad /\ mlkem_co_selected TT.CO1.i TT.CO1.queried RO.RO.m mm rr) => //.
  conseq (mlkem_co_real_selected mm rr) (_ : TT.CO1.bad ==> TT.CO1.bad) => //.
  proc; inline *; auto; progress; smt().
qed.

lemma mlkem_co_fake_after mm rr : phoare [TT.CO1(RO.RO).get :
  TT.CO1.bad /\ mlkem_co_selected TT.CO1.i TT.CO1.queried RO.RO.m mm rr ==>
  TT.CO1.bad /\ mlkem_co_selected TT.CO1.i TT.CO1.queried RO.RO.m mm rr] = 1%r.
proof.
  conseq mlkem_co_fake_ll
    (_ : TT.CO1.bad /\ mlkem_co_selected TT.CO1.i TT.CO1.queried RO.RO.m mm rr ==>
         TT.CO1.bad /\ mlkem_co_selected TT.CO1.i TT.CO1.queried RO.RO.m mm rr) => //.
  conseq (mlkem_co_fake_selected mm rr) (_ : TT.CO1.bad ==> TT.CO1.bad) => //.
  proc; sp; if; if; inline *; auto.
qed.

section MlkemCorrSelectionGame.
declare module QSD <: MlkemCorrDriver{-TT.CO1, -RO.RO, -RO.FRO}.

lemma mlkem_co_selected_game :
  (forall (HH <: TT.PKEROM.POracle{-QSD}),
    islossless HH.get => islossless QSD(HH).run) =>
  equiv [MlkemCorrSelected(QSD,MlkemCoReal(RO.RO)).main ~
    MlkemCorrSelected(QSD,TT.CO1(RO.RO)).main :
    ={glob QSD} ==> ={res}].
proof.
  move=> qll; proc; wp.
  call (_ : TT.CO1.bad,
    ={TT.CO1.bad,TT.CO1.i,TT.CO1.pk,TT.CO1.sk,TT.CO1.queried,RO.RO.m} /\
    mlkem_co_before TT.CO1.i{2} TT.CO1.queried{2} RO.RO.m{2},
    ={TT.CO1.i,TT.CO1.pk,TT.CO1.sk} /\ TT.CO1.bad{1} /\ TT.CO1.bad{2} /\
    mlkem_co_pair TT.CO1.i{2} TT.CO1.queried{1} TT.CO1.queried{2} RO.RO.m{1} RO.RO.m{2}).
  + proc*; call mlkem_co_selection_get; auto; progress; smt().
  + move=> &2 hb.
    conseq (mlkem_co_real_after (nth witness TT.CO1.queried{2} TT.CO1.i{2})
      (oget RO.RO.m{2}.[nth witness TT.CO1.queried{2} TT.CO1.i{2}])) => />;
      rewrite ?mlkem_co_pair_fixed; smt().
  + move=> &1.
    conseq (mlkem_co_fake_after (nth witness TT.CO1.queried{1} TT.CO1.i{1})
      (oget RO.RO.m{1}.[nth witness TT.CO1.queried{1} TT.CO1.i{1}])) => />;
      rewrite /mlkem_co_pair /mlkem_co_selected; smt(some_oget).
  inline *; auto.
  move=> &1 &2 hg; rewrite /=.
  move=> ss hs; rewrite hs /=.
  move=> ii hi; rewrite hi hg /=.
  split.
  + rewrite /mlkem_co_before /=.
    have h0 : 0 <= ii by move: hi; rewrite DInterval.supp_dinter; smt().
    split; first exact h0.
    split; first exact h0.
    move=> xx; apply FMap.mem_empty.
  move=> _ ql bl qsl fl qr br qsr fr hp.
  case br => hbr.
  + move: hp; rewrite hbr /mlkem_co_pair /mlkem_co_selected /=; smt(some_oget).
  move: hp; rewrite hbr /=; smt().
qed.
end section MlkemCorrSelectionGame.

lemma mlkem_corr_drive_ll (QQ <: TT.PKEROM.CORR_ADV)
    (HH <: TT.PKEROM.POracle{-QQ}) :
  (forall (HR <: TT.PKEROM.POracle{-QQ}),
    islossless HR.get => islossless QQ(HR).find) =>
  islossless HH.get => islossless MlkemCorrDrive(QQ,HH).run.
proof. move=> qll hll; proc; call hll; call (qll HH hll); auto. qed.

lemma mlkem_u_wide_ll : islossless H2BOWMod(RO1E.FunRO).get2.
proof. proc; inline *; islossless; apply dkey_ll. qed.

lemma mlkem_u_cache_dec
    (HL <: KEMROMx2.POracle_x2) (HR <: KEMROMx2.POracle_x2) :
  equiv [UU2(HL).dec ~ UU2(HR).dec :
    ={arg,UU2.lD} ==> ={res,UU2.lD}].
proof. proc; sim. qed.

lemma mlkem_u_cache_dec_ll (HH <: KEMROMx2.POracle_x2) :
  islossless UU2(HH).dec.
proof. by proc; inline *; islossless; apply dkey_ll. qed.

lemma mlkem_u_wide_bad : phoare [H2BOWMod(RO1E.FunRO).get2 :
  H1.bad ==> H1.bad] = 1%r.
proof.
  conseq mlkem_u_wide_ll (_ : H1.bad ==> H1.bad) => //.
  proc; inline *; auto; progress; smt().
qed.

section MlkemUInversionGame.
declare module QIV <: KEMROMx2.CCA_ADV{
  -KEMROMx2.CCA, -RO1E.FunRO, -KEMROMx2.RO1.RO, -KEMROMx2.RO2.RO,
  -RF.RF, -UU2, -H1, -H2, -Gm2, -Gm3, -H2BOWMod, -CountHx2}.

lemma mlkem_u_wide_game :
  (forall (HH <: KEMROMx2.POracle_x2{-QIV}) (OO <: KEMROMx2.CCA_ORC{-QIV}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless QIV(HH,OO).guess) =>
  equiv [Gm3(H2(RO1E.FunRO),UU2,QIV).main ~ MlkemUWiden(QIV).main :
    ={glob QIV} ==> !H1.bad{1} /\ H2.invert{1} => res{2}].
proof.
  move=> qll; proc.
  inline Gm3(H2BOWMod(RO1E.FunRO),UU2,QIV).main.
  wp; rnd; wp.
  call (_ : H1.bad,
    ={H1.bad,RO1E.FunRO.f,KEMROMx2.CCA.sk,KEMROMx2.CCA.cstar,H2.mtgt,
      KEMROMx2.RO2.RO.m,UU2.lD} /\
    KEMROMx2.CCA.cstar{1} <> None /\
    oget KEMROMx2.CCA.cstar{1} = enc (RO1E.FunRO.f{1} H2.mtgt{1})
      KEMROMx2.CCA.sk{1}.`1.`1 H2.mtgt{1} /\
    dec KEMROMx2.CCA.sk{1}.`1.`2 (oget KEMROMx2.CCA.cstar{1}) = Some H2.mtgt{1} /\
    mlkem_u_record_inv H2.mtgt{1} KEMROMx2.RO2.RO.m{2} H2.invert{1}
      H2BOWMod.crd{2} H2BOWMod.mf{2},
    ={H1.bad}).
  + by move=> HH OO oll h1ll h2ll; exact (qll HH OO h1ll h2ll oll).
  + proc; sp; if.
    + by smt().
    + call (mlkem_u_cache_dec (<: H2(RO1E.FunRO))
        (<: H2BOWMod(RO1E.FunRO))); auto; progress; smt().
    by auto; smt().
  + move=> &2 hb; proc; sp; if; last by auto.
    call mlkem_u_dec_sim_ll; auto.
  + move=> &1; proc; sp; if; last by auto.
    call (mlkem_u_cache_dec_ll (<: H2BOWMod(RO1E.FunRO))); auto; progress; smt().
  + by proc; auto; smt().
  + by move=> &2 hb; proc; auto.
  + by move=> &1; proc; auto.
  + proc*.
    exlim KEMROMx2.CCA.sk{1}.`1 => ss.
    exlim H2.mtgt{1} => tt.
    exlim (oget KEMROMx2.CCA.cstar{1}) => cc.
    call (mlkem_u_wide_get ss tt cc); auto; progress; smt(some_oget).
  + move=> &2 hb.
    conseq (mlkem_u_sticky_flags true false) => />; smt().
  + move=> &1.
    conseq mlkem_u_wide_bad => />; smt().
  inline *; auto.
  rewrite /mlkem_u_record_inv /b2i; progress; smt(FMap.mem_empty).
qed.

lemma mlkem_u_inversion_wide_bound &m :
  (forall (HH <: KEMROMx2.POracle_x2{-QIV}) (OO <: KEMROMx2.CCA_ORC{-QIV}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless QIV(HH,OO).guess) =>
  Pr[Gm3(H2(RO1E.FunRO),UU2,QIV).main() @ &m : H2.invert] <=
  Pr[MlkemUWiden(QIV).main() @ &m : res] +
  Pr[Gm3(H2(RO1E.FunRO),UU2,QIV).main() @ &m : H1.bad].
proof.
  move=> qll.
  have hg : Pr[Gm3(H2(RO1E.FunRO),UU2,QIV).main() @ &m : H2.invert /\ !H1.bad] <=
    Pr[MlkemUWiden(QIV).main() @ &m : res].
  + byequiv (mlkem_u_wide_game qll) => //; smt().
  have hb : Pr[Gm3(H2(RO1E.FunRO),UU2,QIV).main() @ &m : H2.invert /\ H1.bad] <=
    Pr[Gm3(H2(RO1E.FunRO),UU2,QIV).main() @ &m : H1.bad].
  + by rewrite Pr[mu_sub].
  rewrite Pr[mu_split H1.bad]; smt().
qed.
end section MlkemUInversionGame.

lemma mlkem_ro_get_entry (mm : plaintext) : hoare [RO.RO.get :
  arg = mm ==> RO.RO.m.[mm] = Some res].
proof.
  proc; inline *; auto; progress; smt(FMap.domE FMap.get_set_sameE some_oget).
qed.

lemma mlkem_co_negative_entry (mm : plaintext) : equiv [
  RO.RO.get ~ TT.CO1(RO.RO).get :
    ={arg, RO.RO.m} /\ arg{1} = mm /\ TT.CO1.i{2} = -1 ==>
    ={res, RO.RO.m} /\ TT.CO1.i{2} = -1 /\ RO.RO.m{1}.[mm] = Some res{1}].
proof.
  conseq mlkem_co_negative_get (mlkem_ro_get_entry mm) => />; smt().
qed.

section MlkemCorrRealTrace.
declare module QRT <: TT.PKEROM.CORR_ADV{-TT.CO1, -RO.RO, -RO.FRO}.

lemma mlkem_ro_draw_ll : islossless RO.RO.get.
proof. by proc; inline *; islossless; apply drand_ll. qed.

lemma mlkem_ro_cached_draw (mm : plaintext) (rr : randomness) :
  phoare [RO.RO.get : arg = mm /\ RO.RO.m.[mm] = Some rr ==> res = rr] = 1%r.
proof.
  conseq mlkem_ro_draw_ll
    (_ : arg = mm /\ RO.RO.m.[mm] = Some rr ==> res = rr) => //.
  proc; inline *; auto.
  move=> &hr [hx hm] vv hv.
  by rewrite hx FMap.domE hm /=.
qed.

lemma mlkem_corr_real_trace : equiv [
  TT.PKEROM.Correctness_Adv(RO.RO,TT.TT,QRT).main ~ MlkemCorrMarked(QRT).main :
    ={glob QRT} ==> res{1} = mlkem_corr_bad_at res{2}.`1 res{2}.`2].
proof.
  proc.
  seq 3 2 : (m{1} = mm{2} /\ pk{1} = TT.CO1.pk{2} /\
    sk{1} = (TT.CO1.pk{2},TT.CO1.sk{2}) /\ ={RO.RO.m} /\ TT.CO1.i{2} = -1).
  + inline TT.Correctness_Adv1(RO.RO,QRT).main'.
    wp; call (_ : ={RO.RO.m} /\ TT.CO1.i{2} = -1).
    + proc*; call mlkem_co_negative_get; auto.
    inline *; auto; progress; smt().
  exlim m{1} => mm0.
  inline TT.TT(RO.RO).enc.
  seq 5 1 : (m{1} = mm{2} /\ m{1} = mm0 /\
    pk{1} = TT.CO1.pk{2} /\ sk{1} = (TT.CO1.pk{2},TT.CO1.sk{2}) /\
    ={RO.RO.m} /\ RO.RO.m{1}.[mm0] <> None /\
    c{1} = enc (oget RO.RO.m{2}.[mm0]) TT.CO1.pk{2} mm0).
  + wp; call (mlkem_co_negative_entry mm0); auto.
    progress; smt(some_oget).
  inline TT.TT(RO.RO).dec; sp.
  case (m'0{1} = Some mm0).
  + rcondt{1} 1; first by auto; smt().
    exlim (oget RO.RO.m{2}.[mm0]) => rr.
    wp; call{1} (mlkem_ro_cached_draw mm0 rr); auto.
    rewrite /mlkem_corr_bad_at; progress; smt(some_oget).
  if{1}.
  + wp; call{1} mlkem_ro_draw_ll; auto.
    rewrite /mlkem_corr_bad_at; progress; smt().
  auto; rewrite /mlkem_corr_bad_at; progress; smt().
qed.

lemma mlkem_corr_trace_bound &m :
  Pr[TT.PKEROM.Correctness_Adv(RO.RO,TT.TT,QRT).main() @ &m : res] <=
  Pr[MlkemCorrTrace(QRT).main() @ &m : mlkem_corr_bad_trace res].
proof.
  have he : Pr[TT.PKEROM.Correctness_Adv(RO.RO,TT.TT,QRT).main() @ &m : res] =
    Pr[MlkemCorrMarked(QRT).main() @ &m : mlkem_corr_bad_at res.`1 res.`2].
  + byequiv (mlkem_corr_real_trace) => //.
  rewrite he; exact (mlkem_corr_marked_bound QRT &m).
qed.
end section MlkemCorrRealTrace.

section MlkemCoConcreteCounts.
declare module QOR <: RO.RO{
  -TT.CO1,-A,-CountH,-CountHx2,-H1,-H2,-UU2,-KEMROMx2.CCA,
  -KEMROMx2.RO2.RO,-RF.RF}.

lemma mlkem_co_abstract_count nn : hoare [TT.CO1(QOR).get :
  TT.CO1.counter = nn ==> TT.CO1.counter = nn+1].
proof.
  proc; sp; if; if; wp; try (call (_ : true)); auto; progress; smt().
qed.

lemma mlkem_h2_abstract_count nn : hoare [H2(TT.CO1(QOR)).get2 :
  TT.CO1.counter = nn ==> TT.CO1.counter = nn+1].
proof.
  proc; wp; rnd; wp; call (mlkem_co_abstract_count nn); auto; progress; smt().
qed.

lemma mlkem_b1_co_uc_inv (off : int) :
  hoare [B1x2(A,CountHx2(BUUC(B1x2(A),TT.CO1(QOR)).H2B),KEMROMx2.CCA(CountHx2(BUUC(B1x2(A),TT.CO1(QOR)).H2B),UU2,B1x2(A)).O).guess :
    TT.CO1.counter <= off + CountHx2.c_ht + CountHx2.c_hu ==>
    TT.CO1.counter <= off + CountHx2.c_ht + CountHx2.c_hu].
proof.
  proc.
  call (_ : TT.CO1.counter <= off + CountHx2.c_ht + CountHx2.c_hu);
    last by inline *; auto.
  + proc; sp; if; last by auto.
    inline *; sp; if; auto; progress; smt().
  proc; wp.
  call (_ : TT.CO1.counter <= off + CountHx2.c_ht + CountHx2.c_hu ==>
    TT.CO1.counter <= off + CountHx2.c_ht + CountHx2.c_hu).
  + proc.
    seq 1 : (TT.CO1.counter <= off + CountHx2.c_ht + CountHx2.c_hu);
      first by inline *; auto.
    if.
    + inline CountHx2.
      exlim TT.CO1.counter => nn.
      wp; call (mlkem_h2_abstract_count (nn+1)).
      wp; call (mlkem_co_abstract_count nn); auto; progress; smt().
    auto.
  auto.
qed.

lemma mlkem_uc_counter :
  (forall (HR <: KEMROM.POracle{-CountH,-A}) (OD <: KEMROM.CCA_ORC{-CountH,-A}),
    hoare [A(CountH(HR),OD).guess : CountH.c_h = 0 ==> CountH.c_h <= qHK]) =>
  hoare [BUUC(B1x2(A),TT.CO1(QOR)).find : TT.CO1.counter = 0 ==>
    TT.CO1.counter <= 2*qHK + 2].
proof.
  move=> hq.
  have hb : hoare [B1x2(A,CountHx2(BUUC(B1x2(A),TT.CO1(QOR)).H2B),KEMROMx2.CCA(CountHx2(BUUC(B1x2(A),TT.CO1(QOR)).H2B),UU2,B1x2(A)).O).guess :
    TT.CO1.counter <= 2 /\ CountHx2.c_ht = 0 /\ CountHx2.c_hu = 0 ==>
    TT.CO1.counter <= 2*qHK + 2].
  + conseq (mlkem_b1x2_counts (<: BUUC(B1x2(A),TT.CO1(QOR)).H2B) (<: KEMROMx2.CCA(CountHx2(BUUC(B1x2(A),TT.CO1(QOR)).H2B),UU2,B1x2(A)).O) hq)
      (mlkem_b1_co_uc_inv 2) => />; smt().
  proc; call hb.
  inline UU2(BUUC(B1x2(A),TT.CO1(QOR)).H2B).enc CountHx2.
  wp; call (mlkem_h2_abstract_count 1).
  inline TT.TT.
  wp; call (mlkem_co_abstract_count 0).
  inline *; auto; progress; smt().
qed.

lemma mlkem_b1_co_uci_inv (off : int) :
  hoare [B1x2(A,CountHx2(BUUCI(B1x2(A),TT.CO1(QOR)).H2B),KEMROMx2.CCA(CountHx2(BUUCI(B1x2(A),TT.CO1(QOR)).H2B),UU2,B1x2(A)).O).guess :
    TT.CO1.counter <= off + CountHx2.c_ht + CountHx2.c_hu ==>
    TT.CO1.counter <= off + CountHx2.c_ht + CountHx2.c_hu].
proof.
  proc.
  call (_ : TT.CO1.counter <= off + CountHx2.c_ht + CountHx2.c_hu);
    last by inline *; auto.
  + proc; sp; if; last by auto.
    inline *; sp; if; auto; progress; smt().
  proc; wp.
  call (_ : TT.CO1.counter <= off + CountHx2.c_ht + CountHx2.c_hu ==>
    TT.CO1.counter <= off + CountHx2.c_ht + CountHx2.c_hu).
  + proc.
    seq 1 : (TT.CO1.counter <= off + CountHx2.c_ht + CountHx2.c_hu);
      first by inline *; auto.
    if.
    + inline CountHx2.
      exlim TT.CO1.counter => nn.
      wp; call (mlkem_h2_abstract_count (nn+1)).
      wp; call (mlkem_co_abstract_count nn); auto; progress; smt().
    auto.
  auto.
qed.

lemma mlkem_uci_counter :
  (forall (HR <: KEMROM.POracle{-CountH,-A}) (OD <: KEMROM.CCA_ORC{-CountH,-A}),
    hoare [A(CountH(HR),OD).guess : CountH.c_h = 0 ==> CountH.c_h <= qHK]) =>
  hoare [BUUCI(B1x2(A),TT.CO1(QOR)).find : TT.CO1.counter = 0 ==>
    TT.CO1.counter <= 2*qHK + 1].
proof.
  move=> hq.
  have hb : hoare [B1x2(A,CountHx2(BUUCI(B1x2(A),TT.CO1(QOR)).H2B),KEMROMx2.CCA(CountHx2(BUUCI(B1x2(A),TT.CO1(QOR)).H2B),UU2,B1x2(A)).O).guess :
    TT.CO1.counter <= 1 /\ CountHx2.c_ht = 0 /\ CountHx2.c_hu = 0 ==>
    TT.CO1.counter <= 2*qHK + 1].
  + conseq (mlkem_b1x2_counts (<: BUUCI(B1x2(A),TT.CO1(QOR)).H2B) (<: KEMROMx2.CCA(CountHx2(BUUCI(B1x2(A),TT.CO1(QOR)).H2B),UU2,B1x2(A)).O) hq)
      (mlkem_b1_co_uci_inv 1) => />; smt().
  proc; call hb.
  inline CountHx2.
  wp; call (mlkem_co_abstract_count 0).
  inline *; auto; progress; smt().
qed.
end section MlkemCoConcreteCounts.

lemma mlkem_b1x2_ll
    (HH <: KEMROMx2.POracle_x2{-A,-CountH})
    (OO <: KEMROMx2.CCA_ORC{-A,-CountH}) :
  (forall (HR <: KEMROM.POracle{-A}) (OD <: KEMROMx2.CCA_ORC{-A}),
    islossless OD.dec => islossless HR.get => islossless A(HR,OD).guess) =>
  islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
  islossless B1x2(A,HH,OO).guess.
proof.
  move=> all h1 h2 hd.
  have hb : islossless B1x2(A,HH,OO).BH.get.
  + proc; inline *; islossless.
  have hh : islossless CountH(B1x2(A,HH,OO).BH).get.
  + proc; wp; call hb; auto.
  proc; call (all (<: CountH(B1x2(A,HH,OO).BH)) OO hd hh).
  inline *; auto.
qed.

lemma mlkem_co_negative_actual : equiv [
  TT.CO1(RO.RO).get ~ MlkemCoActual(RO.RO).get :
    ={arg,RO.RO.m,TT.CO1.queried} /\ TT.CO1.i{1} = -1 ==>
    ={res,RO.RO.m,TT.CO1.queried} /\ TT.CO1.i{1} = -1].
proof.
  proc; sp; if{1}.
  + rcondf{1} ^if; first by auto; smt(List.size_ge0).
    inline *; auto; progress; smt().
  rcondt{1} ^if; first by auto; smt(List.find_ge0).
  inline *; auto; progress; smt().
qed.

section MlkemCoGuessGames.
declare module QGG <: TT.PKEROM.CORR_ADV{-TT.CO1,-RO.RO,-RO.FRO}.

lemma mlkem_co_actual_real : equiv [
  MlkemCorrSelected(MlkemCorrDrive(QGG),MlkemCoActual(RO.RO)).main ~
  MlkemCorrSelected(MlkemCorrDrive(QGG),MlkemCoReal(RO.RO)).main :
    ={glob QGG} ==> ={res}].
proof.
  proc; wp.
  call (_ : ={glob QGG,TT.CO1.pk,TT.CO1.sk,TT.CO1.i,TT.CO1.queried,RO.RO.m}).
  + by inline *; sim.
  inline *; auto; progress; smt().
qed.

lemma mlkem_co_guess_real : equiv [
  MlkemCorrGuess.Guess(MlkemCorrTrace(QGG)).main ~
  MlkemCorrSelected(MlkemCorrDrive(QGG),MlkemCoActual(RO.RO)).main :
    ={glob QGG} ==>
    (mlkem_corr_bad_trace res{1}.`2 /\
      res{1}.`1 = mlkem_corr_bad_index res{1}.`2) => res{2}].
proof.
  proc; swap{2} 2 5; wp; rnd; wp.
  inline MlkemCorrTrace(QGG).main
    TT.Correctness_Adv1(RO.RO,QGG).main
    TT.Correctness_Adv1(RO.RO,QGG).main'
    MlkemCorrDrive(QGG,MlkemCoActual(RO.RO)).run.
  wp; call mlkem_co_negative_actual.
  wp; call (_ : ={RO.RO.m,TT.CO1.queried} /\ TT.CO1.i{1} = -1).
  + proc*; call mlkem_co_negative_actual; auto.
  inline *; auto.
  rewrite /DInterval.dinter /List.Range.range /=
    /mlkem_corr_bad_trace /mlkem_corr_bad_index /mlkem_corr_bad_at;
    progress; smt(List.has_find List.nth_find List.find_ge0).
qed.

lemma mlkem_corr_trace_size qb :
  hoare [QGG(TT.CO1(RO.RO)).find : TT.CO1.counter = 0 ==> TT.CO1.counter <= qb] =>
  hoare [MlkemCorrTrace(QGG).main : true ==> size res.`3 <= qb+1].
proof.
  move=> hc.
  have hs : hoare [MlkemCorrTrace(QGG).main : true ==> size res.`3 <= TT.CO1.counter].
  + proc; inline TT.Correctness_Adv1(RO.RO,QGG).main.
    call mlkem_co_size_real.
    inline TT.Correctness_Adv1(RO.RO,QGG).main'; wp.
    call (_ : size TT.CO1.queried <= TT.CO1.counter).
    + exact mlkem_co_size_real.
    inline *; auto.
  have ht : hoare [MlkemCorrTrace(QGG).main : true ==> TT.CO1.counter <= qb+1].
  + proc; inline TT.Correctness_Adv1(RO.RO,QGG).main.
    call (mlkem_co_count_bound_real qb).
    inline TT.Correctness_Adv1(RO.RO,QGG).main'; wp; call hc.
    inline *; auto.
  conseq hs ht => />; smt().
qed.

lemma mlkem_corr_trace_capped &m :
  hoare [QGG(TT.CO1(RO.RO)).find : TT.CO1.counter = 0 ==> TT.CO1.counter <= TT.qHC] =>
  Pr[MlkemCorrTrace(QGG).main() @ &m : mlkem_corr_bad_trace res] =
  Pr[MlkemCorrTrace(QGG).main() @ &m :
    mlkem_corr_bad_trace res /\ size res.`3 <= TT.qHC+1].
proof.
  move=> hc.
  byequiv (_ : ={glob QGG} ==> ={res} /\ size res{2}.`3 <= TT.qHC+1) => //.
  conseq (_ : ={glob QGG} ==> ={res}) (_ : true ==> true)
    (mlkem_corr_trace_size TT.qHC hc) => //.
  proc; sim.
qed.
end section MlkemCoGuessGames.

op mlkem_co_full (qs : plaintext list) (fm : (plaintext,randomness) fmap) =
  forall xx, xx \in qs <=> xx \in fm.

lemma mlkem_co_full_get : hoare [TT.CO1(RO.RO).get :
  mlkem_co_full TT.CO1.queried RO.RO.m ==>
  mlkem_co_full TT.CO1.queried RO.RO.m].
proof.
  proc; sp; if; if; inline *; auto; rewrite /mlkem_co_full;
    progress; smt(List.mem_cat FMap.mem_set).
qed.

section MlkemCoFakeBase.
declare module QFB <: TT.PKEROM.CORR_ADV{-TT.CO1,-RO.RO,-RO.FRO}.

lemma mlkem_co_full_find : hoare [TT.B(QFB,RO.RO).find : true ==>
  mlkem_co_full TT.CO1.queried RO.RO.m].
proof.
  proc; call mlkem_co_full_get.
  inline TT.Correctness_Adv1(RO.RO,QFB).main'; wp.
  call (_ : mlkem_co_full TT.CO1.queried RO.RO.m).
  + exact mlkem_co_full_get.
  inline *; auto; rewrite /mlkem_co_full; progress; smt(FMap.mem_empty).
qed.

lemma mlkem_co_fake_base : equiv [
  MlkemCorrSelected(MlkemCorrDrive(QFB),TT.CO1(RO.RO)).main ~ TT.B(QFB,RO.RO).main :
    ={glob QFB} ==> res{1} => res{2}].
proof.
  proc.
  seq 7 2 : (={TT.CO1.pk,TT.CO1.sk,TT.CO1.i,TT.CO1.queried,RO.RO.m} /\
    mlkem_co_full TT.CO1.queried{2} RO.RO.m{2} /\
    m{2} = mlkem_co_pick TT.CO1.i{2} TT.CO1.queried{2}).
  + conseq (_ : ={glob QFB} ==>
      ={TT.CO1.pk,TT.CO1.sk,TT.CO1.i,TT.CO1.queried,RO.RO.m} /\
      m{2} = mlkem_co_pick TT.CO1.i{2} TT.CO1.queried{2})
      (_ : true ==> true)
      (_ : true ==> mlkem_co_full TT.CO1.queried RO.RO.m) => //.
    + call mlkem_co_full_find; inline *; auto.
    inline *; wp.
    conseq (_ : ={glob QFB} ==>
      ={TT.CO1.pk,TT.CO1.sk,TT.CO1.i,TT.CO1.queried,RO.RO.m}) => />.
    sim.
  case (0 <= TT.CO1.i{2} < size TT.CO1.queried{2}).
  + inline *; auto; rewrite /mlkem_co_pick /mlkem_co_full;
      progress; smt(List.mem_nth FMap.domE FMap.get_setE drand_ll).
  inline *; auto; rewrite /mlkem_co_pick; progress; smt(drand_ll).
qed.

lemma mlkem_corr_adaptive_bound &m :
  (forall (HH <: TT.PKEROM.POracle{-QFB}),
    islossless HH.get => islossless QFB(HH).find) =>
  hoare [QFB(TT.CO1(RO.RO)).find : TT.CO1.counter = 0 ==> TT.CO1.counter <= TT.qHC] =>
  Pr[TT.PKEROM.Correctness_Adv(RO.RO,TT.TT,QFB).main() @ &m : res] <=
  (TT.qHC+1)%r * Pr[TT.B(QFB,RO.RO).main() @ &m : res].
proof.
  move=> qll hc.
  have ht := mlkem_corr_trace_bound QFB &m.
  have hcapped := mlkem_corr_trace_capped QFB &m hc.
  have hf := mlkem_corr_guess_factor QFB &m.
  have hg : Pr[MlkemCorrGuess.Guess(MlkemCorrTrace(QFB)).main() @ &m :
    (mlkem_corr_bad_trace res.`2 /\ size res.`2.`3 <= TT.qHC+1) /\
    res.`1 = mlkem_corr_bad_index res.`2] <=
    Pr[MlkemCorrSelected(MlkemCorrDrive(QFB),MlkemCoActual(RO.RO)).main() @ &m : res].
  + byequiv (mlkem_co_guess_real QFB) => //; smt().
  have ha : Pr[MlkemCorrSelected(MlkemCorrDrive(QFB),MlkemCoActual(RO.RO)).main() @ &m : res] =
    Pr[MlkemCorrSelected(MlkemCorrDrive(QFB),MlkemCoReal(RO.RO)).main() @ &m : res].
  + byequiv (mlkem_co_actual_real QFB) => //.
  have hs : Pr[MlkemCorrSelected(MlkemCorrDrive(QFB),MlkemCoReal(RO.RO)).main() @ &m : res] =
    Pr[MlkemCorrSelected(MlkemCorrDrive(QFB),TT.CO1(RO.RO)).main() @ &m : res].
  + byequiv (mlkem_co_selected_game (MlkemCorrDrive(QFB)) _) => //.
    by move=> HH hll; apply (mlkem_corr_drive_ll QFB HH qll hll).
  have hb : Pr[MlkemCorrSelected(MlkemCorrDrive(QFB),TT.CO1(RO.RO)).main() @ &m : res] <=
    Pr[TT.B(QFB,RO.RO).main() @ &m : res].
  + byequiv mlkem_co_fake_base => //.
  have hnonneg : 0%r <= (TT.qHC+1)%r by smt(TT.ge0_qHC).
  smt().
qed.
end section MlkemCoFakeBase.

module MlkemOWEager(QQ : TT.PKEROM.PCVA_ADV, G : KEMROMx2.RO1.RO) = {
  module H = {
    proc init() = {}
    proc get = G.get
  }
  proc distinguish = TT.PKEROM.OW_PCVA(H,TT.TT,QQ).main
}.

section MlkemOWOracleChange.
declare module QEO <: TT.PKEROM.PCVA_ADV{
  -RO1E.FunRO,-KEMROMx2.RO1.RO,-KEMROMx2.RO1.FRO,-RO.RO,-RO.FRO,
  -TT.PKEROM.OW_PCVA}.

lemma mlkem_ow_eager &m :
  Pr[TT.PKEROM.OW_PCVA(KEMROMx2.RO1.RO,TT.TT,QEO).main() @ &m : res] =
  Pr[TT.PKEROM.OW_PCVA(RO1E.FunRO,TT.TT,QEO).main() @ &m : res].
proof.
  have hll : forall (x : plaintext), is_lossless drand by move=> x; apply drand_ll.
  have h1 := RO1E.pr_RO_FinRO_D hll (MlkemOWEager(QEO)) &m () (fun b => b).
  have h2 := RO1E.pr_FinRO_FunRO_D hll (MlkemOWEager(QEO)) &m () (fun b => b).
  have hl : Pr[TT.PKEROM.OW_PCVA(KEMROMx2.RO1.RO,TT.TT,QEO).main() @ &m : res] =
    Pr[KEMROMx2.RO1.MainD(MlkemOWEager(QEO),KEMROMx2.RO1.RO).distinguish() @ &m : res].
  + byequiv (_ : ={glob QEO} ==> ={res}) => //.
    proc; inline *; wp.
    sim.
  have hr : Pr[TT.PKEROM.OW_PCVA(RO1E.FunRO,TT.TT,QEO).main() @ &m : res] =
    Pr[KEMROMx2.RO1.MainD(MlkemOWEager(QEO),RO1E.FunRO).distinguish() @ &m : res].
  + byequiv (_ : ={glob QEO} ==> ={res}) => //.
    proc; inline *; wp.
    conseq (_ : ={glob QEO} ==>
      ={m',TT.PKEROM.OW_PCVA.sk,TT.PKEROM.OW_PCVA.cc,RO1E.FunRO.f}) => />.
    sim.
  smt().
qed.

lemma mlkem_ow_ro_rename : equiv [
  TT.PKEROM.OW_PCVA(KEMROMx2.RO1.RO,TT.TT,QEO).main ~
  TT.PKEROM.OW_PCVA(RO.RO,TT.TT,QEO).main :
    ={glob QEO} ==> ={res}].
proof.
  proc.
  seq 5 5 : (={m',TT.PKEROM.OW_PCVA.sk,TT.PKEROM.OW_PCVA.cc} /\
    KEMROMx2.RO1.RO.m{1} = RO.RO.m{2}).
  + call (_ : ={TT.PKEROM.OW_PCVA.sk,TT.PKEROM.OW_PCVA.cc} /\
      KEMROMx2.RO1.RO.m{1} = RO.RO.m{2}).
    + by proc; inline *; sim (: KEMROMx2.RO1.RO.m{1} = RO.RO.m{2}).
    + by proc; inline *; sim (: KEMROMx2.RO1.RO.m{1} = RO.RO.m{2}).
    + by proc; inline *; auto.
    inline *; auto.
  inline *; sim (: KEMROMx2.RO1.RO.m{1} = RO.RO.m{2}).
qed.

lemma mlkem_ow_fun_ro &m :
  Pr[TT.PKEROM.OW_PCVA(RO1E.FunRO,TT.TT,QEO).main() @ &m : res] =
  Pr[TT.PKEROM.OW_PCVA(RO.RO,TT.TT,QEO).main() @ &m : res].
proof.
  rewrite -(mlkem_ow_eager &m).
  byequiv mlkem_ow_ro_rename => //.
qed.
end section MlkemOWOracleChange.

section MlkemUReductionLossless.
declare module QLL <: KEMROMx2.CCA_ADV{
  -KEMROMx2.CCA,-KEMROMx2.RO2.RO,-RF.RF,-UU2,-H1,-H2,-H2BOWMod,-CountHx2}.
declare module QLH <: TT.PKEROM.POracle{-QLL,-CountHx2}.

lemma mlkem_uc_ll :
  (forall (HH <: KEMROMx2.POracle_x2{-QLL}) (OO <: KEMROMx2.CCA_ORC{-QLL}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless QLL(HH,OO).guess) =>
  islossless QLH.get => islossless BUUC(QLL,QLH).find.
proof.
  move=> qll hll.
  have h1 : islossless CountHx2(BUUC(QLL,QLH).H2B).get1.
  + proc; wp; call hll; auto.
  have h2 : islossless CountHx2(BUUC(QLL,QLH).H2B).get2.
  + proc; inline *; islossless.
  have hd : islossless KEMROMx2.CCA(CountHx2(BUUC(QLL,QLH).H2B),UU2,QLL).O.dec.
  + proc; inline *; islossless.
  proc; call (qll (<: CountHx2(BUUC(QLL,QLH).H2B))
    (<: KEMROMx2.CCA(CountHx2(BUUC(QLL,QLH).H2B),UU2,QLL).O) h1 h2 hd).
  inline *; islossless.
qed.

lemma mlkem_uci_ll :
  (forall (HH <: KEMROMx2.POracle_x2{-QLL}) (OO <: KEMROMx2.CCA_ORC{-QLL}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless QLL(HH,OO).guess) =>
  islossless QLH.get => islossless BUUCI(QLL,QLH).find.
proof.
  move=> qll hll.
  have h1 : islossless CountHx2(BUUCI(QLL,QLH).H2B).get1.
  + proc; wp; call hll; auto.
  have h2 : islossless CountHx2(BUUCI(QLL,QLH).H2B).get2.
  + proc; inline *; islossless.
  have hd : islossless KEMROMx2.CCA(CountHx2(BUUCI(QLL,QLH).H2B),UU2,QLL).O.dec.
  + proc; inline *; islossless.
  proc; call (qll (<: CountHx2(BUUCI(QLL,QLH).H2B))
    (<: KEMROMx2.CCA(CountHx2(BUUCI(QLL,QLH).H2B),UU2,QLL).O) h1 h2 hd).
  inline *; islossless.
qed.

lemma mlkem_uuow_ll (OO <: TT.PKEROM.VA_ORC) :
  (forall (HH <: KEMROMx2.POracle_x2{-QLL}) (OD <: KEMROMx2.CCA_ORC{-QLL}),
    islossless HH.get1 => islossless HH.get2 => islossless OD.dec =>
    islossless QLL(HH,OD).guess) =>
  islossless QLH.get => islossless BUUOWMod(QLL,QLH,OO).find.
proof.
  move=> qll hll.
  have h1 : islossless CountHx2(BUUOWMod(QLL,QLH,OO).H2B).get1.
  + proc; wp; call hll; auto.
  have h2 : islossless CountHx2(BUUOWMod(QLL,QLH,OO).H2B).get2.
  + proc; inline *; islossless.
  have hd : islossless KEMROMx2.CCA(CountHx2(BUUOWMod(QLL,QLH,OO).H2B),UU2,QLL).O.dec.
  + proc; inline *; islossless.
  proc; call (qll (<: CountHx2(BUUOWMod(QLL,QLH,OO).H2B))
    (<: KEMROMx2.CCA(CountHx2(BUUOWMod(QLL,QLH,OO).H2B),UU2,QLL).O) h1 h2 hd).
  inline *; islossless.
qed.
end section MlkemUReductionLossless.

lemma mlkem_u_wide_secret : equiv [
  H2BOWMod(RO1E.FunRO).get2 ~ H2BOWMod(RO1E.FunRO).get2 :
    ={arg,RO1E.FunRO.f,KEMROMx2.CCA.cstar,KEMROMx2.RO2.RO.m,UU2.lD,
      H2BOWMod.crd,H2BOWMod.mf} /\
    KEMROMx2.CCA.sk{1}.`1.`1 = KEMROMx2.CCA.sk{2}.`1.`1 ==>
    ={res,KEMROMx2.RO2.RO.m,UU2.lD,H2BOWMod.crd,H2BOWMod.mf}].
proof. proc; inline *; auto; progress; smt(). qed.

lemma mlkem_u_cache_dec_cipher
    (HL <: KEMROMx2.POracle_x2) (HR <: KEMROMx2.POracle_x2) :
  equiv [UU2(HL).dec ~ UU2(HR).dec :
    arg{1}.`2 = arg{2}.`2 /\ ={UU2.lD} ==> ={res,UU2.lD}].
proof. proc; sim. qed.

section MlkemUWideOW.
declare module QWO <: KEMROMx2.CCA_ADV{
  -KEMROMx2.CCA,-RO1E.FunRO,-KEMROMx2.RO1.RO,-KEMROMx2.RO2.RO,
  -RF.RF,-UU2,-H1,-H2,-Gm2,-Gm3,-H2BOWMod,-CountHx2,-TT.PKEROM.OW_PCVA}.

lemma mlkem_u_wide_ow : equiv [
  MlkemUWiden(QWO).main ~ TT.PKEROM.OW_PCVA(RO1E.FunRO,TT.TT,BUUOWMod(QWO)).main :
    ={glob QWO} ==> res{1} => res{2}].
proof.
  proc; inline *; wp; rnd{1}; wp.
  call (_ : ={RO1E.FunRO.f,KEMROMx2.RO2.RO.m,UU2.lD,KEMROMx2.CCA.cstar,
      H2BOWMod.crd,H2BOWMod.mf} /\
    KEMROMx2.CCA.sk{1}.`1.`1 = KEMROMx2.CCA.sk{2}.`1.`1 /\
    KEMROMx2.CCA.sk{1}.`1 = TT.PKEROM.OW_PCVA.sk{2} /\
    KEMROMx2.CCA.cstar{1} = Some TT.PKEROM.OW_PCVA.cc{2} /\
    TT.PKEROM.OW_PCVA.cc{2} = enc (RO1E.FunRO.f{1} H2.mtgt{1})
      KEMROMx2.CCA.sk{1}.`1.`1 H2.mtgt{1}).
  + proc; sp; if; first by smt().
    + call (mlkem_u_cache_dec_cipher (<: H2BOWMod(RO1E.FunRO))
        (<: CountHx2(BUUOWMod(QWO,RO1E.FunRO,
          TT.PKEROM.OW_PCVA(RO1E.FunRO,TT.TT,BUUOWMod(QWO)).O).H2B)));
        auto; progress; smt().
    auto; progress; smt().
  + by proc; inline *; auto.
  + proc*; inline CountHx2; wp; call mlkem_u_wide_secret; auto; progress; smt().
  swap{1} 16 -3.
  auto; progress; smt(DBool.dbool_ll some_oget).
qed.
end section MlkemUWideOW.

section MlkemTHashBound.
declare module QTH <: KEMROMx2.CCA_ADV{
  -KEMROMx2.CCA,-RO1E.FunRO,-KEMROMx2.RO1.RO,-KEMROMx2.RO2.RO,
  -RF.RF,-UU2,-H1,-H2,-Gm2,-Gm3,-H2BOWMod,-CountHx2,
  -RO.RO,-RO.FRO,-TT.CO1,-TT.Gm,-TT.PKEROM.OW_PCVA,
  -TT.PKE.OW_CPA,-TT.PKE.OWL_CPA,-TT.O_AdvOW,-TT.CountO}.

lemma mlkem_t_pcva_adapter &m :
  Pr[TT.PKEROM.OW_PCVA(RO.RO,TT.TT,BUUOWMod(QTH)).main() @ &m : res] =
  Pr[TT.PKEROM.OW_PCVA(RO.RO,TT.TT,MlkemHashPCVA(MlkemHashOWU(QTH))).main() @ &m : res].
proof. byequiv => //; proc; inline *; sim. qed.

lemma mlkem_t_ow_adapter &m :
  Pr[TT.PKE.OW_CPA(TT.BasePKE,TT.AdvOW(MlkemHashPCVA(MlkemHashOWU(QTH)))).main() @ &m : res] =
  Pr[TT.PKE.OW_CPA(TT.BasePKE,TT.AdvOW(BUUOWMod(QTH))).main() @ &m : res].
proof. byequiv => //; proc; inline *; sim. qed.

lemma mlkem_t_owl_adapter &m :
  Pr[TT.PKE.OWL_CPA(TT.BasePKE,TT.AdvOWL_query(MlkemHashPCVA(MlkemHashOWU(QTH)))).main() @ &m : res] =
  Pr[TT.PKE.OWL_CPA(TT.BasePKE,TT.AdvOWL_query(BUUOWMod(QTH))).main() @ &m : res].
proof. byequiv => //; proc; inline *; sim. qed.

lemma mlkem_t_hash_bound &m :
  (forall (HH <: KEMROMx2.POracle_x2{-QTH}) (OO <: KEMROMx2.CCA_ORC{-QTH}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless QTH(HH,OO).guess) =>
  0 < TT.qH + TT.qP =>
  Pr[TT.PKEROM.OW_PCVA(RO.RO,TT.TT,BUUOWMod(QTH)).main() @ &m : res] <=
  Pr[TT.PKE.OW_CPA(TT.BasePKE,TT.AdvOW(BUUOWMod(QTH))).main() @ &m : res] +
  Pr[TT.PKE.OWL_CPA(TT.BasePKE,TT.AdvOWL_query(BUUOWMod(QTH))).main() @ &m : res].
proof.
  move=> qll hq.
  have hfind : forall (HH <: TT.PKEROM.POracle{-MlkemHashOWU(QTH)}),
    islossless HH.get => islossless MlkemHashOWU(QTH,HH).find.
  + move=> HH hll; exact (mlkem_uuow_ll QTH HH MlkemNoVA qll hll).
  have hv : Pr[TT.PKEROM.OW_PCVA(RO.RO,TT.TT,MlkemHashPCVA(MlkemHashOWU(QTH))).main() @ &m : res] <=
    Pr[MlkemTGame(MlkemHashOWU(QTH)).main(true) @ &m : res].
  + byequiv (mlkem_t_validation (MlkemHashOWU(QTH))) => //.
  have ht := mlkem_t_program_bound (MlkemHashOWU(QTH)) &m hfind.
  have ho := mlkem_t_base_ow (MlkemHashOWU(QTH)) &m.
  have hl := mlkem_t_base_query (MlkemHashOWU(QTH)) &m hq.
  have ha := mlkem_t_pcva_adapter &m.
  have hb := mlkem_t_ow_adapter &m.
  have hc := mlkem_t_owl_adapter &m.
  smt().
qed.
end section MlkemTHashBound.

module MlkemPinnedQueryH = CountHx2(
  BUUOWMod(B1x2(A),TT.CountH(RO.RO),TT.CountO(TT.O_AdvOW)).H2B).
module MlkemPinnedQueryO = KEMROMx2.CCA(MlkemPinnedQueryH,UU2,B1x2(A)).O.

lemma mlkem_query_domain_inv :
  hoare [B1x2(A,MlkemPinnedQueryH,MlkemPinnedQueryO).guess :
    RO.RO.m = empty ==> FMap.fsize RO.RO.m <= CountH.c_h].
proof.
  proc.
  call (_ : FMap.fsize RO.RO.m <= CountH.c_h);
    last by inline *; auto; progress; smt(FMap.fsize_empty).
  + proc; sp; if; last by auto.
    inline *; sp; if; auto; progress; smt().
  proc; wp.
  call (_ : FMap.fsize RO.RO.m <= CountH.c_h ==>
    FMap.fsize RO.RO.m <= CountH.c_h + 1).
  + proc.
    seq 1 : (FMap.fsize RO.RO.m <= CountH.c_h); first by inline *; auto.
    if.
    + inline *; auto; progress;
        smt(FMap.fsize_set FMap.domE FMap.get_setE FMap.set_set_sameE).
    auto; progress; smt().
  auto.
qed.

lemma mlkem_query_domain_budget :
  (forall (HR <: KEMROM.POracle{-CountH, -A}) (OD <: KEMROM.CCA_ORC{-CountH, -A}),
    hoare [A(CountH(HR),OD).guess : CountH.c_h = 0 ==> CountH.c_h <= qHK]) =>
  hoare [B1x2(A,MlkemPinnedQueryH,MlkemPinnedQueryO).guess :
    RO.RO.m = empty ==> FMap.fsize RO.RO.m <= qHK].
proof.
  move=> hq.
  conseq mlkem_query_domain_inv
    (mlkem_b1x2_budget
      (<: BUUOWMod(B1x2(A),TT.CountH(RO.RO),TT.CountO(TT.O_AdvOW)).H2B)
      MlkemPinnedQueryO hq) => />; smt().
qed.

lemma mlkem_uuow_domain :
  (forall (HR <: KEMROM.POracle{-CountH, -A}) (OD <: KEMROM.CCA_ORC{-CountH, -A}),
    hoare [A(CountH(HR),OD).guess : CountH.c_h = 0 ==> CountH.c_h <= qHK]) =>
  hoare [BUUOWMod(B1x2(A),TT.CountH(RO.RO),TT.CountO(TT.O_AdvOW)).find :
    RO.RO.m = empty ==> FMap.fsize RO.RO.m <= qHK].
proof.
  move=> hq; proc; call (mlkem_query_domain_budget hq).
  inline *; auto.
qed.

lemma mlkem_query_list_size :
  (forall (HR <: KEMROM.POracle{-CountH, -A}) (OD <: KEMROM.CCA_ORC{-CountH, -A}),
    hoare [A(CountH(HR),OD).guess : CountH.c_h = 0 ==> CountH.c_h <= qHK]) =>
  hoare [TT.AdvOWL_query(BUUOWMod(B1x2(A))).find : true ==> size res <= qHK].
proof.
  move=> hq; proc; inline TT.AdvOW_query(BUUOWMod(B1x2(A))).find
    TT.AdvOW_query(BUUOWMod(B1x2(A))).main.
  wp; rnd; call (mlkem_uuow_domain hq).
  inline *; auto; rewrite /FMap.fsize; progress; smt(FSet.cardE).
qed.

section MlkemUProbabilityBound.
declare module QUP <: KEMROMx2.CCA_ADV{
  -KEMROMx2.CCA,-RO1E.FunRO,-KEMROMx2.RO1.RO,-KEMROMx2.RO1.FRO,-KEMROMx2.RO2.RO,
  -RF.RF,-UU2,-H1,-H2,-Gm2,-Gm3,-H2BOWMod,-CountHx2,
  -RO.RO,-RO.FRO,-TT.PKEROM.OW_PCVA}.

lemma mlkem_u_challenge_gap &m :
  (forall (HH <: KEMROMx2.POracle_x2{-QUP}) (OO <: KEMROMx2.CCA_ORC{-QUP}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless QUP(HH,OO).guess) =>
  `|Pr[Gm2(H2(RO1E.FunRO),UU2,QUP).main() @ &m : res] -
    Pr[Gm3(H2(RO1E.FunRO),UU2,QUP).main() @ &m : res]| <=
    Pr[Gm3(H2(RO1E.FunRO),UU2,QUP).main() @ &m : H2.invert].
proof.
  move=> qll.
  have hl : Pr[Gm2(H2(RO1E.FunRO),UU2,QUP).main() @ &m : res] <=
    Pr[Gm3(H2(RO1E.FunRO),UU2,QUP).main() @ &m : res \/ H2.invert].
  + byequiv (mlkem_u_challenge_game QUP qll) => //; smt().
  have hr : Pr[Gm3(H2(RO1E.FunRO),UU2,QUP).main() @ &m : res /\ !H2.invert] <=
    Pr[Gm2(H2(RO1E.FunRO),UU2,QUP).main() @ &m : res].
  + byequiv (_ : ={glob QUP} ==> res{1} /\ !H2.invert{1} => res{2}) => //.
    symmetry; conseq (mlkem_u_challenge_game QUP qll) => //; smt().
  have hn : 0%r <= Pr[Gm3(H2(RO1E.FunRO),UU2,QUP).main() @ &m : res /\ H2.invert]
    by rewrite Pr[mu_ge0].
  have hb : Pr[Gm3(H2(RO1E.FunRO),UU2,QUP).main() @ &m : res /\ H2.invert] <=
    Pr[Gm3(H2(RO1E.FunRO),UU2,QUP).main() @ &m : H2.invert]
    by rewrite Pr[mu_sub].
  move: hl; rewrite Pr[mu_or] => hl.
  have hs : Pr[Gm3(H2(RO1E.FunRO),UU2,QUP).main() @ &m : res] =
    Pr[Gm3(H2(RO1E.FunRO),UU2,QUP).main() @ &m : res /\ H2.invert] +
    Pr[Gm3(H2(RO1E.FunRO),UU2,QUP).main() @ &m : res /\ !H2.invert]
    by rewrite Pr[mu_split H2.invert].
  smt().
qed.

lemma mlkem_u_security_core &m :
  (forall (HH <: KEMROMx2.POracle_x2{-QUP}) (OO <: KEMROMx2.CCA_ORC{-QUP}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless QUP(HH,OO).guess) =>
  `|Pr[Gm1(RO_x2E,QUP).main() @ &m : res] - 1%r/2%r| <=
  Pr[TT.PKEROM.Correctness_Adv(RO.RO,TT.TT,BUUC(QUP)).main() @ &m : res] +
  Pr[TT.PKEROM.Correctness_Adv(RO.RO,TT.TT,BUUCI(QUP)).main() @ &m : res] +
  Pr[TT.PKEROM.OW_PCVA(RO.RO,TT.TT,BUUOWMod(QUP)).main() @ &m : res].
proof.
  move=> qll.
  have hi : Pr[Gm1(RO_x2E,QUP).main() @ &m : res] =
    Pr[Gm2(H1,UU1(RF.RF),QUP).main2() @ &m : res].
  + byequiv (mlkem_u_instrument QUP) => //.
  have hs := mlkem_u_smooth_gap QUP &m qll.
  have hc := mlkem_u_challenge_gap &m qll.
  have hget1 : islossless H2(RO1E.FunRO).get1 by proc; auto.
  have hdec : islossless KEMROMx2.CCA(H2(RO1E.FunRO),UU2,QUP).O.dec.
  + proc; sp; if; last by auto.
    call mlkem_u_dec_sim_ll; auto.
  have hguess := qll (<: H2(RO1E.FunRO))
    (<: KEMROMx2.CCA(H2(RO1E.FunRO),UU2,QUP).O)
    hget1 mlkem_u_get2_sim_ll hdec.
  have hf := mlkem_u_fair_half QUP &m hguess.
  have hv := mlkem_u_inversion_wide_bound QUP &m qll.
  have hw : Pr[MlkemUWiden(QUP).main() @ &m : res] <=
    Pr[TT.PKEROM.OW_PCVA(RO1E.FunRO,TT.TT,BUUOWMod(QUP)).main() @ &m : res].
  + byequiv (mlkem_u_wide_ow QUP) => //.
  have huc := mlkem_uc_bad_bound QUP &m.
  have hci := mlkem_uci_bad_bound QUP &m.
  have hrc := mlkem_corr_fun_ro (BUUC(QUP)) &m.
  have hri := mlkem_corr_fun_ro (BUUCI(QUP)) &m.
  have hro := mlkem_ow_fun_ro (BUUOWMod(QUP)) &m.
  have htri := mlkem_real_triangle
    (Pr[Gm2(H2(RO1E.FunRO),UU2,QUP).main() @ &m : res])
    (Pr[Gm2(H1,UU1(RF.RF),QUP).main2() @ &m : res]) (1%r/2%r).
  smt().
qed.
end section MlkemUProbabilityBound.

lemma mlkem_b_find_ll (QQ <: TT.PKEROM.CORR_ADV{-TT.CO1,-RO.RO,-RO.FRO}) :
  (forall (HH <: TT.PKEROM.POracle{-QQ}),
    islossless HH.get => islossless QQ(HH).find) =>
  islossless TT.B(QQ,RO.RO).find.
proof.
  move=> qll; proc; call mlkem_co_fake_ll.
  inline TT.Correctness_Adv1(RO.RO,QQ).main'; wp.
  call (qll (<: TT.CO1(RO.RO)) mlkem_co_fake_ll).
  inline *; islossless; apply DInterval.dinter_ll; exact TT.ge0_qHC.
qed.

section MlkemAdaptiveBase.
declare module QAB <: TT.PKEROM.CORR_ADV{-TT.CO1,-RO.RO,-RO.FRO}.

lemma mlkem_corr_adaptive_base &m :
  (forall (HH <: TT.PKEROM.POracle{-QAB}),
    islossless HH.get => islossless QAB(HH).find) =>
  hoare [QAB(TT.CO1(RO.RO)).find : TT.CO1.counter = 0 ==> TT.CO1.counter <= TT.qHC] =>
  hoare [QAB(TT.CO1(RO.LRO)).find : TT.CO1.counter = 0 ==> TT.CO1.counter <= TT.qHC] =>
  TT.qHC < TT.FinT.card - 1 =>
  Pr[TT.PKEROM.Correctness_Adv(RO.RO,TT.TT,QAB).main() @ &m : res] <=
  (TT.qHC+1)%r * Pr[TT.PKE.Correctness_Adv(TT.BasePKE,TT.B(QAB,RO.RO)).main() @ &m : res].
proof.
  move=> qll hqr hql hcard.
  have ha := mlkem_corr_adaptive_bound QAB &m qll hqr.
  have he := mlkem_corr_main_lazy QAB &m.
  have hsz := mlkem_co_find_bound_lazy QAB TT.qHC hql.
  have hl : Pr[TT.B(QAB,RO.LRO).main() @ &m : res] =
    Pr[TT.PKE.Correctness_Adv(TT.BasePKE,TT.B(QAB,RO.LRO)).main() @ &m : res].
  + byequiv (mlkem_corr_lazy_base QAB hcard hsz) => //.
  have hr := mlkem_corr_base_lazy QAB &m.
  smt().
qed.
end section MlkemAdaptiveBase.

module MlkemFinalListQ = TT.AdvOWL_query(BUUOWMod(B1x2(A))).
module MlkemFinalOW = TT.AdvOW(BUUOWMod(B1x2(A))).
module MlkemFinalListO = OWvsIND.BL(MlkemFinalOW).
module MlkemFinalCorrO = BOWp(TT.BasePKE,MlkemFinalOW).
module MlkemFinalCorrU = TT.B(BUUC(B1x2(A)),RO.RO).
module MlkemFinalCorrI = TT.B(BUUCI(B1x2(A)),RO.RO).

lemma mlkem_final_ow_ll :
  (forall (HH <: KEMROMx2.POracle_x2{-B1x2(A)}) (OO <: KEMROMx2.CCA_ORC{-B1x2(A)}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless B1x2(A,HH,OO).guess) =>
  islossless MlkemFinalOW.find.
proof.
  move=> qll; proc.
  call (mlkem_uuow_ll (B1x2(A)) (<: TT.CountH(RO.RO))
    (<: TT.CountO(TT.O_AdvOW)) qll _).
  + proc; inline *; islossless.
  inline *; auto.
qed.

lemma mlkem_final_list_ll :
  (forall (HH <: KEMROMx2.POracle_x2{-B1x2(A)}) (OO <: KEMROMx2.CCA_ORC{-B1x2(A)}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless B1x2(A,HH,OO).guess) =>
  0 < TT.qH + TT.qP => islossless MlkemFinalListQ.find.
proof.
  move=> qll hq; proc.
  inline TT.AdvOW_query(BUUOWMod(B1x2(A))).find
    TT.AdvOW_query(BUUOWMod(B1x2(A))).main.
  wp; rnd.
  call (mlkem_uuow_ll (B1x2(A)) (<: TT.CountH(RO.RO))
    (<: TT.CountO(TT.O_AdvOW)) qll _).
  + proc; inline *; islossless.
  inline *; auto; progress.
  apply DInterval.dinter_ll; smt().
qed.
  (* SCRATCHPAD END *)
lemma conclusion &m fail_prob prg_kg_bound prg_enc_bound :

    Pr[ CorrectnessBound.main() @ &m : res] <= fail_prob =>

   `| Pr[PRG_KG.IND(PRG_KG.PRGr, DC_KG(BOWp(TT.BasePKE, TT.AdvOW_query(BUUOWMod(B1x2(A)))))).main() @ &m : res] -
       Pr[PRG_KG.IND(PRG_KG.PRGi, DC_KG(BOWp(TT.BasePKE, TT.AdvOW_query(BUUOWMod(B1x2(A)))))).main() @ &m : res] | <= prg_kg_bound =>
   `| Pr[PRG_KG.IND(PRG_KG.PRGr, DC_KG(BOWp(TT.BasePKE, TT.AdvOW(BUUOWMod(B1x2(A)))))).main() @ &m : res] -
       Pr[PRG_KG.IND(PRG_KG.PRGi, DC_KG(BOWp(TT.BasePKE, TT.AdvOW(BUUOWMod(B1x2(A)))))).main() @ &m : res]  | <= prg_kg_bound =>
   `| Pr[PRG_KG.IND(PRG_KG.PRGr, DC_KG(TT.B(TT.AdvCorr(BUUOWMod(B1x2(A))), RO.RO))).main() @ &m : res] -
       Pr[PRG_KG.IND(PRG_KG.PRGi, DC_KG(TT.B(TT.AdvCorr(BUUOWMod(B1x2(A))), RO.RO))).main() @ &m : res]  | <= prg_kg_bound =>
   `| Pr[PRG_KG.IND(PRG_KG.PRGr, DC_KG(TT.B(BUUCI(B1x2(A)), RO.RO))).main() @ &m : res] -
       Pr[PRG_KG.IND(PRG_KG.PRGi, DC_KG(TT.B(BUUCI(B1x2(A)), RO.RO))).main() @ &m : res]  | <= prg_kg_bound =>
   `| Pr[PRG_KG.IND(PRG_KG.PRGr, DC_KG(TT.B(BUUC(B1x2(A)), RO.RO))).main() @ &m : res] -
       Pr[PRG_KG.IND(PRG_KG.PRGi, DC_KG(TT.B(BUUC(B1x2(A)), RO.RO))).main() @ &m : res]  | <= prg_kg_bound =>
   `|Pr[PRG_KG.IND(PRG_KG.PRGr, D_KG(OWvsIND.Bowl(OWvsIND.BL(TT.AdvOW(BUUOWMod(B1x2(A))))))).main() @ &m : res] -
       Pr[PRG_KG.IND(PRG_KG.PRGi, D_KG(OWvsIND.Bowl(OWvsIND.BL(TT.AdvOW(BUUOWMod(B1x2(A))))))).main() @ &m : res]| <=  prg_kg_bound =>
   `|Pr[PRG_KG.IND(PRG_KG.PRGr, D_KG(OWvsIND.Bowl(TT.AdvOWL_query(BUUOWMod(B1x2(A)))))).main() @ &m : res] -
       Pr[PRG_KG.IND(PRG_KG.PRGi, D_KG(OWvsIND.Bowl(TT.AdvOWL_query(BUUOWMod(B1x2(A)))))).main() @ &m : res]|  <=  prg_kg_bound =>
   `| Pr[PRG_ENC.IND(PRG_ENC.PRGr, DC_ENC(BOWp(TT.BasePKE, TT.AdvOW_query(BUUOWMod(B1x2(A)))))).main() @ &m : res] -
       Pr[PRG_ENC.IND(PRG_ENC.PRGi, DC_ENC(BOWp(TT.BasePKE, TT.AdvOW_query(BUUOWMod(B1x2(A)))))).main() @ &m : res]|  <= prg_enc_bound =>
   `| Pr[PRG_ENC.IND(PRG_ENC.PRGr, DC_ENC(BOWp(TT.BasePKE, TT.AdvOW(BUUOWMod(B1x2(A)))))).main() @ &m : res] -
       Pr[PRG_ENC.IND(PRG_ENC.PRGi, DC_ENC(BOWp(TT.BasePKE, TT.AdvOW(BUUOWMod(B1x2(A)))))).main() @ &m : res] |  <= prg_enc_bound =>
   `| Pr[PRG_ENC.IND(PRG_ENC.PRGr, DC_ENC(TT.B(TT.AdvCorr(BUUOWMod(B1x2(A))), RO.RO))).main() @ &m : res] -
       Pr[PRG_ENC.IND(PRG_ENC.PRGi, DC_ENC(TT.B(TT.AdvCorr(BUUOWMod(B1x2(A))), RO.RO))).main() @ &m : res] |  <= prg_enc_bound =>
   `| Pr[PRG_ENC.IND(PRG_ENC.PRGr, DC_ENC(TT.B(BUUCI(B1x2(A)), RO.RO))).main() @ &m : res] -
       Pr[PRG_ENC.IND(PRG_ENC.PRGi, DC_ENC(TT.B(BUUCI(B1x2(A)), RO.RO))).main() @ &m : res] |  <= prg_enc_bound =>
   `| Pr[PRG_ENC.IND(PRG_ENC.PRGr, DC_ENC(TT.B(BUUC(B1x2(A)), RO.RO))).main() @ &m : res] -
       Pr[PRG_ENC.IND(PRG_ENC.PRGi, DC_ENC(TT.B(BUUC(B1x2(A)), RO.RO))).main() @ &m : res] |  <= prg_enc_bound =>
   `|Pr[IND(PRG_ENC.PRGr, D_ENC(OWvsIND.Bowl(OWvsIND.BL(TT.AdvOW(BUUOWMod(B1x2(A))))))).main() @ &m : res] -
       Pr[IND(PRG_ENC.PRGi, D_ENC(OWvsIND.Bowl(OWvsIND.BL(TT.AdvOW(BUUOWMod(B1x2(A))))))).main() @ &m : res]|  <= prg_enc_bound =>
   `|Pr[IND(PRG_ENC.PRGr, D_ENC(OWvsIND.Bowl(TT.AdvOWL_query(BUUOWMod(B1x2(A)))))).main() @ &m : res] -
       Pr[IND(PRG_ENC.PRGi, D_ENC(OWvsIND.Bowl(TT.AdvOWL_query(BUUOWMod(B1x2(A)))))).main() @ &m : res]|   <= prg_enc_bound =>


    qHT = qHK =>
    qHU = qHK =>
    TT.qH = qHT + qHU + 1 =>
    TT.qV = 0 =>
    TT.qP = 0 =>
    TT.qH + 1 = TT.qHC =>
    TT.qHC < TT.FinT.card - 1 =>

    (forall (RO0 <: KEMROM.POracle{-CountH, -A} ) (O0 <: KEMROM.CCA_ORC{-CountH, -A} ),
       hoare[ A(CountH(RO0), O0).guess : CountH.c_h = 0 ==> CountH.c_h <= qHK]) =>

    (forall (H0 <: KEMROM.POracle{-A} ) (O <: KEMROMx2.CCA_ORC{-A} ),
       islossless O.dec => islossless H0.get => islossless A(H0, O).guess) =>

    `|Pr[KEMROM.CCA(KEMROM.RO.RO, FO_K, A).main() @ &m : res] - 1%r / 2%r| <=
    2%r * (`| Pr[MLWE_H(B1(OWvsIND.Bowl(TT.AdvOWL_query(BUUOWMod(B1x2(A)))))).main(false, false) @ &m : res] -
             Pr[MLWE_H(B1(OWvsIND.Bowl(TT.AdvOWL_query(BUUOWMod(B1x2(A)))))).main(false, true) @ &m : res] | +
          `| Pr[MLWE_H(B2(OWvsIND.Bowl(TT.AdvOWL_query(BUUOWMod(B1x2(A)))))).main(true, false) @ &m : res] -
             Pr[MLWE_H(B2(OWvsIND.Bowl(TT.AdvOWL_query(BUUOWMod(B1x2(A)))))).main(true, true) @ &m : res] | +
             prg_kg_bound + prg_enc_bound) +
    2%r * (`| Pr[MLWE_H(B1(OWvsIND.Bowl(OWvsIND.BL(TT.AdvOW(BUUOWMod(B1x2(A))))))).main(false, false) @ &m : res] -
             Pr[MLWE_H(B1(OWvsIND.Bowl(OWvsIND.BL(TT.AdvOW(BUUOWMod(B1x2(A))))))).main(false, true) @ &m : res] | +
           `| Pr[MLWE_H(B2(OWvsIND.Bowl(OWvsIND.BL(TT.AdvOW(BUUOWMod(B1x2(A))))))).main(true, false) @ &m : res] -
             Pr[MLWE_H(B2(OWvsIND.Bowl(OWvsIND.BL(TT.AdvOW(BUUOWMod(B1x2(A))))))).main(true, true) @ &m : res]| +
            prg_kg_bound + prg_enc_bound) +
    (3%r * (2*qHK + 3)%r + 1%r) * (fail_prob + prg_kg_bound + prg_enc_bound) +
    `|Pr[J.IND(PseudoRF.PRF, D(B1x2(A))).main() @ &m : res] - Pr[J.IND(RF.RF, D(B1x2(A))).main() @ &m : res]| +
    2%r * (2*qHK + 2)%r * eps_msg.
proof.
  move=> hf kgqw kgow kgadv kgci kguc kgbl kgql
    encqw encow encadv encci encuc encbl encql
    hht hhu hqhv hqv hqp hqhc hcard hcount all.
  have q2 : forall (HH <: KEMROMx2.POracle_x2{-B1x2(A)})
      (OO <: KEMROMx2.CCA_ORC{-B1x2(A)}),
    islossless HH.get1 => islossless HH.get2 => islossless OO.dec =>
    islossless B1x2(A,HH,OO).guess.
  + move=> HH OO h1 h2 hd; exact (mlkem_b1x2_ll HH OO all h1 h2 hd).
  have qcu : forall (HH <: TT.PKEROM.POracle{-BUUC(B1x2(A))}),
    islossless HH.get => islossless BUUC(B1x2(A),HH).find.
  + move=> HH hh; exact (mlkem_uc_ll (B1x2(A)) HH q2 hh).
  have qci : forall (HH <: TT.PKEROM.POracle{-BUUCI(B1x2(A))}),
    islossless HH.get => islossless BUUCI(B1x2(A),HH).find.
  + move=> HH hh; exact (mlkem_uci_ll (B1x2(A)) HH q2 hh).
  have hcap : TT.qHC = 2*qHK+2 by smt().
  have hpos : 0 < TT.qH + TT.qP by smt(ge0_qHK).
  have quR : hoare [BUUC(B1x2(A),TT.CO1(RO.RO)).find :
    TT.CO1.counter = 0 ==> TT.CO1.counter <= TT.qHC].
  + conseq (mlkem_uc_counter (<: RO.RO) hcount) => />; smt().
  have quL : hoare [BUUC(B1x2(A),TT.CO1(RO.LRO)).find :
    TT.CO1.counter = 0 ==> TT.CO1.counter <= TT.qHC].
  + conseq (mlkem_uc_counter (<: RO.LRO) hcount) => />; smt().
  have qiR : hoare [BUUCI(B1x2(A),TT.CO1(RO.RO)).find :
    TT.CO1.counter = 0 ==> TT.CO1.counter <= TT.qHC].
  + conseq (mlkem_uci_counter (<: RO.RO) hcount) => />; smt().
  have qiL : hoare [BUUCI(B1x2(A),TT.CO1(RO.LRO)).find :
    TT.CO1.counter = 0 ==> TT.CO1.counter <= TT.qHC].
  + conseq (mlkem_uci_counter (<: RO.LRO) hcount) => />; smt().
  have acu := mlkem_corr_adaptive_base (BUUC(B1x2(A))) &m qcu quR quL hcard.
  have aci := mlkem_corr_adaptive_base (BUUCI(B1x2(A))) &m qci qiR qiL hcard.
  have bcu := mlkem_correctness_bound MlkemFinalCorrU &m fail_prob prg_kg_bound prg_enc_bound
    (mlkem_b_find_ll (BUUC(B1x2(A))) qcu) hf kguc encuc.
  have bci := mlkem_correctness_bound MlkemFinalCorrI &m fail_prob prg_kg_bound prg_enc_bound
    (mlkem_b_find_ll (BUUCI(B1x2(A))) qci) hf kgci encci.
  have bco := mlkem_correctness_bound MlkemFinalCorrO &m fail_prob prg_kg_bound prg_enc_bound
    (mlkem_bowp_ll MlkemFinalOW) hf kgow encow.
  rewrite -(mlkem_base_corr MlkemFinalCorrU &m) in bcu.
  rewrite -(mlkem_base_corr MlkemFinalCorrI &m) in bci.
  rewrite -(mlkem_base_corr MlkemFinalCorrO &m) in bco.
  have oll := mlkem_final_ow_ll q2.
  have qll := mlkem_final_list_ll q2 hpos.
  have bll := mlkem_bl_ll MlkemFinalOW oll.
  have ow := mlkem_ow_to_list MlkemFinalOW &m oll.
  have lq := mlkem_list_to_ind MlkemFinalListQ &m qHK ge0_qHK qll
    (mlkem_query_list_size hcount).
  have lo := mlkem_list_to_ind MlkemFinalListO &m 1 _ bll
    (mlkem_bl_size MlkemFinalOW); first by smt().
  have cq := mlkem_cpa_bound (OWvsIND.Bowl(MlkemFinalListQ)) &m prg_kg_bound prg_enc_bound
    (mlkem_bowl_choose_ll MlkemFinalListQ) (mlkem_bowl_guess_ll MlkemFinalListQ qll) kgql encql.
  have co := mlkem_cpa_bound (OWvsIND.Bowl(MlkemFinalListO)) &m prg_kg_bound prg_enc_bound
    (mlkem_bowl_choose_ll MlkemFinalListO) (mlkem_bowl_guess_ll MlkemFinalListO bll) kgbl encbl.
  rewrite -(mlkem_base_cpa (OWvsIND.Bowl(MlkemFinalListQ)) &m) in cq.
  rewrite -(mlkem_base_cpa (OWvsIND.Bowl(MlkemFinalListO)) &m) in co.
  have ut := mlkem_u_security_core (B1x2(A)) &m q2.
  have tb := mlkem_t_hash_bound (B1x2(A)) &m q2 hpos.
  have hsplit := mlkem_split_cca &m.
  have lazy2 := mlkem_lazy_second &m.
  have lazy1 := mlkem_lazy_first &m.
  have lazycca : Pr[CCAL(KEMROMx2.RO1.LRO,KEMROMx2.RO2.LRO,B1x2(A)).main() @ &m : res] =
    Pr[KEMROMx2.CCA(KEMROMx2.RO_x2(KEMROMx2.RO1.RO,KEMROMx2.RO2.RO),UU,B1x2(A)).main() @ &m : res].
  + byequiv mlkem_lazy_cca => //.
  have prfreal : Pr[KEMROMx2.CCA(KEMROMx2.RO_x2(KEMROMx2.RO1.RO,KEMROMx2.RO2.RO),UU,B1x2(A)).main() @ &m : res] =
    Pr[J.IND(PseudoRF.PRF,D(B1x2(A))).main() @ &m : res].
  + byequiv mlkem_u_prf_real => //.
  have prfrandom := mlkem_u_prf_random &m.
  have heager := mlkem_u_eager &m.
  have tr := mlkem_real_triangle
    (Pr[J.IND(RF.RF,D(B1x2(A))).main() @ &m : res])
    (Pr[J.IND(PseudoRF.PRF,D(B1x2(A))).main() @ &m : res]) (1%r/2%r).
  have hcorrect : 0%r <= fail_prob + prg_kg_bound + prg_enc_bound.
  + have hz : 0%r <= Pr[TT.PKE.Correctness_Adv(TT.BasePKE,MlkemFinalCorrO).main() @ &m : res]
      by rewrite Pr[mu_ge0].
    smt().
  have heps : 0%r <= TT.PKE.eps_msg.
  + have := ge0_mu1 TT.dplaintext witness; rewrite mlkem_plaintext_mass; smt().
  have hncap : 0%r <= (TT.qHC+1)%r by smt(TT.ge0_qHC).
  smt(ge0_qHK).
qed.

end section.
end MLWE_PKE_Hash.
