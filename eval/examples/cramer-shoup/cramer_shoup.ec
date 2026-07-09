require import AllCore List Distr Dexcepted PKE.
require import StdOrder StdBigop.
import RField RealOrder Bigreal.

require TCR RndExcept.

(** DiffieHellman *)
require DiffieHellman.
clone DiffieHellman as DH.
import DH.DDH DH.G DH.GP DH.FD DH.GP.ZModE.

clone DH.GP.ZModE.ZModpField as ZPF.

lemma gt1_q : 1 < order by smt(ge2_p).

theory Ad1.

  clone import RndExcept as RndE with
    type input <- unit,
    type t     <- exp,
    op   d     <- fun _ => dt,
    type out   <- bool
    proof *.
    realize d_ll. move=> _;apply dt_ll. qed.

  clone include Adversary1_1 with
    op n <- order
    proof *.
  realize gt1_n by apply gt1_q.
  realize d_uni.
  proof.
  move=> _ x; rewrite dt1E.
  suff: size elems = size elems by smt().
  apply uniq_size_uniq; rewrite ?elems_uniq.
  by smt(elemsP elemsP).
  qed.

end Ad1.

theory DDH_ex.

  module DDH0_ex (A:Adversary) = {
    proc main() : bool = {
      var b, x, y;
      x <$ dt \ (pred1 zero);
      y <$ dt;
      b <@ A.guess(g ^ x, g ^ y, g ^ (x * y));
      return b;
    }
  }.

  module DDH1_ex (A:Adversary) = {
    proc main() : bool = {
      var b, x, y, z;

      x <$ dt \ (pred1 zero);
      y <$ dt;
      z <$ dt;
      b <@ A.guess(g ^ x, g ^ y, g ^ z);
      return b;
    }
  }.

  section PROOFS.

  declare module A <: Adversary.

  declare axiom A_ll : islossless A.guess.

  local module Addh0 : Ad1.ADV = {
    proc a1 () = { return ((), zero); }
    proc a2 (x : exp) = {
      var b, y;
      y <$ dt;
      b <@ A.guess(g ^ x, g ^ y, g ^ (x * y));
      return b;
    }
  }.

  local module Addh1 = {
    proc a1 = Addh0.a1
    proc a2 (x : exp) = {
      var b, y, z;
      y <$ dt;
      z <$ dt;
      b <@ A.guess(g ^ x, g ^ y, g ^ z);
      return b;
    }
  }.

  local lemma a1_ll : islossless Addh0.a1.
  proof. proc;auto. qed.

  lemma adv_DDH_DDH_ex &m :
     `| Pr[DDH0_ex(A).main()@ &m : res] - Pr[DDH1_ex(A).main()@ &m : res] | <=
     `| Pr[DDH0(A).main()@ &m : res] - Pr[DDH1(A).main()@ &m : res] | + 2%r / order%r.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    have h0: `|Pr[DDH0_ex(A).main()@ &m : res] - Pr[DDH0(A).main()@ &m : res]| <= 1%r / order%r.
    + (* excepted distribution bound: sampling dt\{0} vs dt differs by <= 1/order *)
      have -> : Pr[DDH0_ex(A).main() @ &m : res] = Pr[Ad1.MainE(Addh0).main() @ &m : res].
      + byequiv => //; proc; inline *; wp; call (_: true); auto.
      have -> : Pr[DDH0(A).main() @ &m : res] = Pr[Ad1.Main(Addh0).main() @ &m : res].
      + byequiv => //; proc; inline *; wp; call (_: true); auto.
      apply (Ad1.pr_abs Addh0 a1_ll _ &m (fun b _ => b)).
      proc; call A_ll; rnd; skip; smt(dt_ll).
    have h1: `|Pr[DDH1_ex(A).main()@ &m : res] - Pr[DDH1(A).main()@ &m : res]| <= 1%r / order%r.
    + (* excepted distribution bound: sampling dt\{0} vs dt differs by <= 1/order *)
      have -> : Pr[DDH1_ex(A).main() @ &m : res] = Pr[Ad1.MainE(Addh1).main() @ &m : res].
      + byequiv => //; proc; inline *; wp; call (_: true); auto.
      have -> : Pr[DDH1(A).main() @ &m : res] = Pr[Ad1.Main(Addh1).main() @ &m : res].
      + byequiv => //; proc; inline *; wp; call (_: true); auto.
      apply (Ad1.pr_abs Addh1 a1_ll _ &m (fun b _ => b)).
      proc; call A_ll; do 2! rnd; skip; smt(dt_ll).
    smt().
  qed.

  end section PROOFS.

end DDH_ex.
import DDH_ex.

(** Target Collision Resistant *)

clone import TCR as TCR_H with
  type t_from <- group * group * group,
  type t_to   <- exp.

axiom dk_ll : is_lossless dk.
hint exact random : dk_ll.

(** Cramer Shoup Encryption *)

clone import PKE as PKE_ with
   type pkey = K * group * group * group * group * group,
   type skey = K * group * group * exp * exp * exp * exp * exp * exp,
   type plaintext = group,
   type ciphertext = group * group * group * group.

module CramerShoup : Scheme = {
  proc kg() : pkey * skey = {
    var x1, x2, y1, y2, z1, z2, k, w, g_, pk, sk;
    x1 <$ dt;
    x2 <$ dt;
    y1 <$ dt;
    y2 <$ dt;
    z1 <$ dt;
    z2 <$ dt;
    w  <$ dt \ (pred1 zero);
    k  <$ dk;
    g_ <- g ^ w;
    pk <- (k, g, g_, g ^ x1 * g_ ^ x2, g ^ y1 * g_ ^ y2, g ^ z1 * g_ ^ z2);
    sk <- (k, g, g_, x1, x2, y1, y2, z1, z2);
    return (pk, sk);
  }

  proc enc(pk : pkey, m : plaintext) : ciphertext = {
    var k, g, g_, e, f, h, u, a, a_, c, v, d;
    (k, g, g_, e, f, h) <- pk;
    u <$ dt;
    a <- g ^ u; a_ <- g_ ^ u;
    c <- h ^ u * m;
    v <- H k (a, a_, c);
    d <- e ^ u * f ^ (u * v);
    return (a, a_, c, d);
  }

  proc dec(sk : skey, ci : ciphertext) = {
    var k, g, g_, x1, x2, y1, y2, z1, z2, a, a_, c, d, v;
    (k, g, g_, x1, x2, y1, y2, z1, z2) <- sk;
    (a, a_, c, d) <- ci;
    v <- H k (a, a_, c);
    return (if d = a ^ (x1 + v * y1) * a_ ^ (x2 + v * y2) then Some (c / (a ^ z1 * a_ ^ z2))
            else None);
  }

}.

(** Correctness of the scheme *)

hoare CramerShoup_correct : Correctness(CramerShoup).main : true ==> res.
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    proc; inline *; auto => /> &hr x1 _ x2 _ y1 _ y2 _ z1 _ z2 _ w _ k _ u _.
    pose v := H k _.
    have -> : (g ^ x1 * g ^ w ^ x2) ^ u * (g ^ y1 * g ^ w ^ y2) ^ (u * v) =
              g ^ u ^ (x1 + v * y1) * g ^ w ^ u ^ (x2 + v * y2).
    + rewrite log_bij !(logg1, logrzM, logDr); ring.
    rewrite /=.
    have -> : (g ^ z1 * g ^ w ^ z2) ^ u = g ^ u ^ z1 * g ^ w ^ u ^ z2.
    + rewrite log_bij !(logg1, logrzM, logDr); ring.
    by rewrite log_bij !(logg1, logrzM, logDr, logDrN, logrV); ring.
qed.

(** IND-CCA Security of the scheme *)

module B_DDH (A:CCA_ADV) = {

  module CCA = CCA(CramerShoup, A)

  proc guess(gx gy gz:group): bool = {
    var g_, a, a_, x1,x2,y1,y2,z1,z2,k,e,f,h,m0,m1,b,b',c,v,d,c',pk;
    x1 <$ dt;
    x2 <$ dt;
    y1 <$ dt;
    y2 <$ dt;
    z1 <$ dt;
    z2 <$ dt;
    g_ <- gx;
    a  <- gy;
    a_ <- gz;
    k  <$ dk;
    e  <- g^x1 * g_^x2;
    f  <- g^y1 * g_^y2;
    h  <- g^z1 * g_^z2;
    CCA.log <- [];
    CCA.cstar <- None;
    pk <- (k, g, g_, g^x1 * g_^x2, g^y1 * g_^y2, g^z1 * g_^z2);
    CCA.sk <- (k, g, g_, x1, x2, y1, y2, z1, z2);
    (m0,m1) <@ CCA.A.choose(pk);
    b <$ {0,1};
    c <- a^z1 * a_^z2 * (b ? m1 : m0);
    v <- H k (a,a_,c);
    d <- a^(x1 + v*y1) * a_^(x2+v*y2);
    c' <- (a,a_,c,d);
    CCA.cstar <- Some c';
    b' <@ CCA.A.guess(c');
    return (b = b');
  }
}.

 module B_TCR (A:CCA_ADV) = {
    var log   : ciphertext list
    var cstar : ciphertext option
    var g3    : ( group * group * group) option
    var g_, a, a_, c, d : group
    var w, u , u', x, y, z, alpha, v' : exp
    var k : K
    module O = {
      proc dec(ci:ciphertext) = {
        var m, a,a_,c,d,v;
        m <- None;
        if (size log < PKE_.qD && Some ci <> cstar) {
          log <- ci :: log;
          (a,a_,c,d) <- ci;
          v <- H k (a, a_, c);
          if (a_ <> a^w /\ v = v' /\ (a,a_,c) <> (B_TCR.a, B_TCR.a_,B_TCR.c)) g3 <- Some (a,a_,c);
          m <- if (a_ = a^w /\ d = a ^ (x + v*y)) then Some (c / a ^ z)
              else None;
        }
        return m;
      }
    }

    module A = A (O)

    proc c1() = {
      var r';
      log <- [];
      g3 <- None;
      cstar <- None;
      w <$ dt \ (pred1 zero);
      u <$ dt;
      u' <$ dt \ (pred1 u);
      g_ <- g ^ w;
      a <- g^u; a_ <- g_^u';
      r' <$ dt; c <- g^r';
      return (a, a_, c);
    }

    proc c2 (k:K) = {
      var m0, m1, b0, e, f, h, r;
      B_TCR.k <- k;
      y <$ dt; f <- g^y;
      z <$ dt; h <- g^z;
      v' <- H k (a, a_, c);
      x <$ dt; r <$ dt; e <- g^x;
      alpha <- (r - u*(x + v'*y))/ (w*(u'-u));
      d <- g ^ r;
      (m0,m1) <@ A.choose(k, g, g_, e, f, h);
      cstar <- Some (a,a_,c,d);
      b0 <@ A.guess(a,a_,c,d);
      return (oget g3);
    }
  }.

lemma CCA_dec_ll (A<:CCA_ADV) : islossless CCA(CramerShoup, A).O.dec.
proof. islossless. qed.

section Security_Aux.

  declare module A <: CCA_ADV {-CCA, -B_TCR}.
  declare axiom guess_ll : forall (O <: CCA_ORC{-A}), islossless O.dec => islossless A(O).guess.
  declare axiom choose_ll : forall (O <: CCA_ORC{-A}), islossless O.dec => islossless A(O).choose.

  equiv CCA_DDH0 : CCA(CramerShoup, A).main ~ DDH0_ex(B_DDH(A)).main : ={glob A} ==> ={res}.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    proc; inline *.
    swap{1} 20 -5.
    wp.
    call (_: ={CCA.log, CCA.cstar, CCA.sk}).
    + by sim.
    wp; rnd.
    call (_: ={CCA.log, CCA.cstar, CCA.sk}).
    + by sim.
    swap{1} 15 -5; swap{1} 9 -6; swap{1} 10 -6.
    auto => />.
    move => wL _ uL _ x1L _ x2L _ y1L _ y2L _ z1L _ z2L _ kL _ result_R bL _.
    have -> : g ^ wL ^ uL = g ^ (wL * uL) by rewrite log_bij !(logg1, logrzM, logDr); ring.
    have -> : (g ^ z1L * g ^ wL ^ z2L) ^ uL = g ^ uL ^ z1L * g ^ (wL * uL) ^ z2L
      by rewrite log_bij !(logg1, logrzM, logDr); ring.
    have -> : forall v, (g ^ x1L * g ^ wL ^ x2L) ^ uL * (g ^ y1L * g ^ wL ^ y2L) ^ (uL * v) =
              g ^ uL ^ (x1L + v * y1L) * g ^ (wL * uL) ^ (x2L + v * y2L)
      by move=> v; rewrite log_bij !(logg1, logrzM, logDr); ring.
    do !split => //; by move => _ _ _ ?; rewrite eq_iff.
  qed.

  lemma pr_CCA_DDH0 &m :
    Pr[CCA(CramerShoup, A).main() @ &m : res] =
    Pr[DDH0_ex(B_DDH(A)).main() @ &m : res].
  proof. by byequiv CCA_DDH0. qed.

  local module G1 = {
    var log     : ciphertext list
    var cstar   : ciphertext option
    var bad     : bool
    var u,u',w  : exp
    var x,x1,x2 : exp
    var y,y1,y2 : exp
    var z,z1,z2 : exp
    var g_: group
    var k       : K

    module O = {
      proc dec(ci:ciphertext) = {
        var m, a,a_,c,d,v;
        m <- None;
        if (size log < PKE_.qD && Some ci <> G1.cstar) {
          log <- ci :: log;
          (a,a_,c,d) <- ci;
          v <- H k (a, a_, c);
          bad <- bad \/ (a_ <> a^w /\ d = a ^ (x1 + v*y1) * a_ ^ (x2 + v * y2));
          m <- if (a_ = a^w /\ d = a ^ (x + v*y)) then Some (c / a ^ z)
              else None;
        }
        return m;
      }
    }

    module A = A(O)

    proc a1 () = {
      log <- [];
      cstar <- None;
      bad <- false;
      w <$ dt \ (pred1 zero);
      u <$ dt;
      return ((),u);
    }

    proc a2 (u0' : exp) = {
      var m0, m1, b, b0, a, a_, c, d, v, e, f, h;
      u' <- u0';
      g_ <- g ^ w; k  <$ dk;
      a <- g^u; a_ <- g_^u';
      x <$ dt; x2 <$ dt; x1 <- x - w * x2; e <- g^x;
      y <$ dt; y2 <$ dt; y1 <- y - w * y2; f <- g^y;
      z <$ dt; z2 <$ dt; z1 <- z - w * z2; h <- g^z;
      (m0,m1) <@ A.choose(k, g, g_, e, f, h);
      b <$ {0,1};
      c <- a^z1 * a_^z2 * (b ? m1 : m0);
      v <- H k (a, a_, c);
      d <- a^(x1 + v*y1) * a_^(x2+v*y2);
      cstar <- Some (a,a_,c,d);
      b0 <@ A.guess(a,a_,c,d);
      return (b = b0);
    }
  }.

  local equiv DDH1_G1_dec :
    CCA(CramerShoup, A).O.dec ~ G1.O.dec :
    ( !G1.bad{2} /\ c{1} = ci{2} /\
      (G1.x{2} = G1.x1{2} + G1.w{2} * G1.x2{2} /\
       G1.y{2} = G1.y1{2} + G1.w{2} * G1.y2{2} /\
       G1.z{2} = G1.z1{2} + G1.w{2} * G1.z2{2}) /\
       CCA.log{1} = G1.log{2} /\ CCA.cstar{1} = G1.cstar{2} /\
       CCA.sk{1} = (G1.k{2}, g, G1.g_{2}, G1.x1{2}, G1.x2{2}, G1.y1{2}, G1.y2{2}, G1.z1{2}, G1.z2{2})) ==>
    (!G1.bad{2} =>
       ={res} /\
       (G1.x{2} = G1.x1{2} + G1.w{2} * G1.x2{2} /\
        G1.y{2} = G1.y1{2} + G1.w{2} * G1.y2{2} /\
        G1.z{2} = G1.z1{2} + G1.w{2} * G1.z2{2}) /\
       CCA.log{1} = G1.log{2} /\ CCA.cstar{1} = G1.cstar{2} /\
       CCA.sk{1} = (G1.k{2}, g, G1.g_{2}, G1.x1{2}, G1.x2{2}, G1.y1{2}, G1.y2{2}, G1.z1{2}, G1.z2{2})).
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  local lemma G1_dec_ll : islossless G1.O.dec.
  proof. by proc;inline *;auto. qed.

  local lemma G1_dec_bad : phoare[ G1.O.dec : G1.bad ==> G1.bad ] = 1%r.
  proof. by proc; auto => ? ->. qed.

  local equiv DDH1_G1 : DDH1_ex(B_DDH(A)).main ~ Ad1.Main(G1).main :
                        ={glob A} ==> !G1.bad{2} => ={res}.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  admit.
  qed.

  lemma dt_r_ll x : is_lossless (dt \ pred1 x).
  proof.
    by rewrite dexcepted_ll ?dt_ll // dt1E ltr_pdivr_mulr /= lt_fromint; smt (gt1_q).
  qed.

  local lemma aux1 &m :
    Pr[CCA(CramerShoup, A).main() @ &m : res] <=
       `| Pr[DDH0(B_DDH(A)).main() @ &m : res] - Pr[DDH1(B_DDH(A)).main() @ &m : res] |
    + Pr[Ad1.MainE(G1).main() @ &m : res \/ G1.bad] + 3%r/order%r.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  local module G2 = {

    module O = G1.O

    module A = G1.A

    var alpha, v: exp

    proc main1 () = {
      var m0, m1, b, b0, v, e, f, h, r', a, a_, c, d;
      G1.log <- [];
      G1.cstar <- None;
      G1.bad <- false;
      G1.w <$ dt \ (pred1 zero);
      G1.u <$ dt;
      G1.u' <$ dt \ (pred1 G1.u);
      G1.g_ <- g ^ G1.w; G1.k  <$ dk;
      a <- g^G1.u; a_ <- G1.g_^G1.u';
      G1.x <$ dt; G1.x2 <$ dt; G1.x1 <- G1.x - G1.w * G1.x2; e <- g^G1.x;
      G1.y <$ dt; G1.y2 <$ dt; G1.y1 <- G1.y - G1.w * G1.y2; f <- g^G1.y;
      G1.z <$ dt; h <- g^G1.z;
      (m0,m1) <@ A.choose(G1.k, g, G1.g_, e, f, h);
      b <$ {0,1};
      r' <$ dt;
      c <- g^r';
      v <- H G1.k (a, a_, c);
      d <- a^(G1.x1 + v*G1.y1) * a_^(G1.x2+v*G1.y2);
      G1.cstar <- Some (a,a_,c,d);
      b0 <@ A.guess(a,a_,c,d);
      return (b = b0);
    }

    proc main () = {
      var m0, m1, b, b0, e, f, h, r, r', a, a_, c, d;
      G1.log <- [];
      G1.cstar <- None;
      G1.bad <- false;
      G1.w <$ dt \ (pred1 zero);
      G1.u <$ dt;
      G1.u' <$ dt \ (pred1 G1.u);
      G1.g_ <- g ^ G1.w; G1.k  <$ dk;
      a <- g^G1.u; a_ <- G1.g_^G1.u';
      G1.y <$ dt; G1.y2 <$ dt; G1.y1 <- G1.y - G1.w * G1.y2; f <- g^G1.y;
      G1.z <$ dt; r' <$ dt; h <- g^G1.z;
      c <- g^r';
      v <- H G1.k (a, a_, c);
      G1.x <$ dt; r <$ dt;
      alpha <- (r - G1.u*(G1.x + v*G1.y))/ (G1.w*(G1.u'-G1.u));
      G1.x2 <- alpha - v*G1.y2;
      G1.x1 <- G1.x - G1.w * G1.x2; e <- g^G1.x;
      d <- g ^ r;
      (m0,m1) <@ A.choose(G1.k, g, G1.g_, e, f, h);
      G1.cstar <- Some (a,a_,c,d);
      b0 <@ A.guess(a,a_,c,d);
      b <$ {0,1};
      return (b = b0);
    }
  }.

  local equiv G1_G21 : Ad1.MainE(G1).main ~ G2.main1 : ={glob A} ==> ={res, G1.bad}.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  local equiv G21_G2 : G2.main1 ~ G2.main : ={glob A} ==> ={res, G1.bad}.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  local lemma pr_G2_res &m: Pr[G2.main() @ &m : res] <= 1%r/2%r.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  local module G3 = {
    var g3 : ( group * group * group) option
    var y2log : exp list
    var cilog : ciphertext list
    var a, a_, c, d: group

    module O = {
      proc dec(ci:ciphertext) = {
        var m, a,a_,c,d,v, y2';
        m <- None;
        if (size G1.log < PKE_.qD && Some ci <> G1.cstar) {
          cilog <- (G1.cstar = None) ? ci :: cilog : cilog;
          G1.log <- ci :: G1.log;
          (a,a_,c,d) <- ci;
          v <- H G1.k (a, a_, c);
          if (a_ <> a^G1.w) {
            if (v = G2.v /\ (a,a_,c) <> (G3.a,G3.a_,G3.c)) g3 <- Some (a,a_,c);
            else {
              y2' <- ((loge d - loge a*(G1.x + v*G1.y))/(loge a_ - loge a*G1.w) - G2.alpha) / (v -G2.v);
              y2log <-  y2' :: y2log;
            }
          }
          m <- if (a_ = a^G1.w /\ d = a ^ (G1.x + v*G1.y)) then Some (c / a ^ G1.z)
              else None;
        }
        return m;
      }
    }

    module A = A (O)

    proc main () = {
      var m0, m1, b0, e, f, h, r, r';
      G1.log <- [];
      G3.y2log <- [];
      G3.cilog <- [];
      G3.g3 <- None;
      G1.cstar <- None;
      G1.w <$ dt \ (pred1 zero);
      G1.u <$ dt;
      G1.u' <$ dt \ (pred1 G1.u);
      G1.g_ <- g ^ G1.w; G1.k  <$ dk;
      a <- g^G1.u; a_ <- G1.g_^G1.u';
      G1.y <$ dt; f <- g^G1.y;
      G1.z <$ dt; r' <$ dt; h <- g^G1.z;
      c <- g^r';
      G2.v <- H G1.k (a, a_, c);
      G1.x <$ dt; r <$ dt; e <- g^G1.x;
      G2.alpha <- (r - G1.u*(G1.x + G2.v*G1.y))/ (G1.w*(G1.u'-G1.u));
      d <- g ^ r;
      (m0,m1) <@ A.choose(G1.k, g, G1.g_, e, f, h);
      G1.cstar <- Some (a,a_,c,d);
      b0 <@ A.guess(a,a_,c,d);
      G1.y2 <$ dt;
      G1.y1 <- G1.y - G1.w * G1.y2;
      G1.x2 <- G2.alpha - G2.v*G1.y2;
      G1.x1 <- G1.x - G1.w * G1.x2;
    }
  }.

  local equiv G2_G3_dec :  G1.O.dec ~ G3.O.dec :
    ! (G3.g3 <> None \/ (G3.a, G3.a_,G3.c, G3.d) \in G3.cilog){2}  /\
    ={ci} /\ ={G1.x, G1.y, G1.z, G1.x1, G1.x2, G1.y1, G1.y2, G1.log, G1.cstar, G1.w,
               G1.u, G1.u', G1.k} /\
    (G1.cstar <> None => G1.cstar = Some (G3.a,G3.a_,G3.c,G3.d)){2} /\
    (G3.d = G3.a^(G1.x1 + G2.v*G1.y1) * G3.a_^(G1.x2+G2.v*G1.y2) /\
     G1.y1 = G1.y - G1.w * G1.y2 /\
     G1.x1 = G1.x - G1.w * G1.x2 /\
     G1.x2 = G2.alpha - G2.v * G1.y2){2} /\
    (G1.bad{1} => G1.y2{2} \in G3.y2log{2}) ==>
    !(G3.g3 <> None \/ (G3.a, G3.a_,G3.c, G3.d) \in G3.cilog){2} =>
     (={res} /\ ={G1.x, G1.y, G1.z, G1.x1, G1.x2, G1.y1, G1.y2, G1.log, G1.cstar, G1.w,
                 G1.u, G1.u', G1.k} /\
      (G1.cstar <> None => G1.cstar = Some (G3.a,G3.a_,G3.c,G3.d)){2} /\
      (G3.d = G3.a^(G1.x1 + G2.v*G1.y1) * G3.a_^(G1.x2+G2.v*G1.y2) /\
       G1.y1 = G1.y - G1.w * G1.y2 /\
       G1.x1 = G1.x - G1.w * G1.x2 /\
       G1.x2 = G2.alpha - G2.v * G1.y2){2} /\
      (G1.bad{1} => G1.y2{2} \in G3.y2log{2})).
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  local equiv G2_G3 : G2.main ~ G3.main :
    ={glob A} ==>
      !(G3.g3 <> None \/ (G3.a, G3.a_,G3.c, G3.d) \in G3.cilog){2} =>
      (G1.bad{1} => (G1.y2 \in G3.y2log){2}).
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  local lemma pr_G3_y2log &m :
    Pr[G3.main() @ &m : G1.y2 \in G3.y2log] <= PKE_.qD%r / order%r.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  local equiv G3_TCR : G3.main ~ TCR(B_TCR(A)).main : ={glob A} ==> G3.g3{1} <> None => res{2}.
  proof.
    proc;inline *;wp;rnd{1}.
    call (_ : B_TCR.log{2} = G1.log{1} /\
              B_TCR.cstar{2} = G1.cstar{1} /\
              B_TCR.k{2} = G1.k{1} /\
              B_TCR.x{2} = G1.x{1} /\ B_TCR.y{2} = G1.y{1} /\ B_TCR.z{2} = G1.z{1} /\
              B_TCR.a{2} = G3.a{1} /\ B_TCR.a_{2} = G3.a_{1} /\ B_TCR.c{2} = G3.c{1} /\
              B_TCR.v'{2} = G2.v{1} /\
              B_TCR.w{2}  = G1.w{1} /\
              B_TCR.g3{2} = G3.g3{1} /\
              (G3.g3{1} <> None =>
               (H B_TCR.k (oget B_TCR.g3) = B_TCR.v' /\ (oget B_TCR.g3) <>
                                                   (B_TCR.a,B_TCR.a_,B_TCR.c)){2})).
    + by proc;auto=> /#.
    wp; call (_ : B_TCR.log{2} = G1.log{1} /\
              B_TCR.cstar{2} = G1.cstar{1} /\
              B_TCR.k{2} = G1.k{1} /\
              B_TCR.x{2} = G1.x{1} /\ B_TCR.y{2} = G1.y{1} /\ B_TCR.z{2} = G1.z{1} /\
              B_TCR.a{2} = G3.a{1} /\ B_TCR.a_{2} = G3.a_{1} /\ B_TCR.c{2} = G3.c{1} /\
              B_TCR.v'{2} = G2.v{1} /\
              B_TCR.w{2}  = G1.w{1} /\
              B_TCR.g3{2} = G3.g3{1} /\
              (G3.g3{1} <> None =>
               (H B_TCR.k (oget B_TCR.g3) = B_TCR.v' /\ (oget B_TCR.g3) <>
                                                   (B_TCR.a,B_TCR.a_,B_TCR.c)){2})).
    + by proc;auto=> /#.
    swap{1} 16 -7;auto; smt(dt_ll).
  qed.


 local module G4 = {

    module O = {
      proc dec(ci:ciphertext) = {
        var m, a,a_,c,d,v;
        m <- None;
        if (size G1.log < PKE_.qD && Some ci <> G1.cstar) {
          G3.cilog <- (G1.cstar = None) ? ci :: G3.cilog : G3.cilog;
          G1.log <- ci :: G1.log;
          (a,a_,c,d) <- ci;
          v <- H G1.k (a, a_, c);
          m <- if (a_ = a^G1.w /\ d = a ^ (G1.x + v*G1.y)) then Some (c / a ^ G1.z)
              else None;
        }
        return m;
      }
    }

    module A = A (O)

    proc main () = {
      var m0, m1, b0, e, f, h, r, r';
      G1.log <- [];
      G3.cilog <- [];
      G1.cstar <- None;
      G1.w <$ dt \ (pred1 zero);
      G1.g_ <- g ^ G1.w;

      G1.k  <$ dk;
      G1.y <$ dt; f <- g^G1.y;
      G1.z <$ dt;  h <- g^G1.z;
      G1.x <$ dt; e <- g^G1.x;
      (m0,m1) <@ A.choose(G1.k, g, G1.g_, e, f, h);
      G1.u <$ dt;
      G1.u' <$ dt \ (pred1 G1.u);
      r' <$ dt;
      r <$ dt;
      G3.a <- g^G1.u; G3.a_ <- G1.g_^G1.u';G3.c <- g^r'; G3.d <- g ^ r;
      G2.v <- H G1.k (G3.a, G3.a_, G3.c);
      G2.alpha <- (r - G1.u*(G1.x + G2.v*G1.y))/ (G1.w*(G1.u'-G1.u));
      G1.cstar <- Some (G3.a,G3.a_,G3.c,G3.d);
      b0 <@ A.guess(G3.a,G3.a_,G3.c,G3.d);
    }
  }.

  local equiv G3_G4 : G3.main ~ G4.main : ={glob A} ==> ={G3.a, G3.a_,G3.c, G3.d, G3.cilog}.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  (* TODO: move this ?*)
  lemma mu_mem_le_mu1_size (dt : 'a distr) (l : 'a list) (r : real) n:
    size l <= n =>
    (forall (x : 'a), mu1 dt x <= r) => mu dt (mem l) <= n%r * r.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    (* induction on l; Mu_mem.mu_mem_le + ler_wpmul2r *)
    move=> h_size h_mu; apply (ler_trans ((size l)%r * r)).
    + by apply (mu_mem_le_mu1 dt l r h_mu).
    apply ler_wpmul2r; first by have := h_mu witness; smt(ge0_mu1).
    by rewrite le_fromint.
  qed.

  local lemma pr_G4 &m:
    Pr[G4.main() @ &m : (G3.a, G3.a_,G3.c, G3.d) \in G3.cilog] <=
      (PKE_.qD%r/order%r)^3 * (PKE_.qD%r/(order-1)%r).
  proof.
    byphoare=> //;proc.
    seq 23 : ((G3.a, G3.a_, G3.c, G3.d) \in G3.cilog)
             ((PKE_.qD%r / order%r)^3 * (PKE_.qD%r / (order - 1)%r)) 1%r _ 0%r => //;last first.
    + hoare; call (_ : G1.cstar <> None /\ !(G3.a, G3.a_, G3.c, G3.d) \in G3.cilog).
      + by proc;auto => /#.
      by auto.
    seq 13 : true 1%r ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r))
                 0%r _ (size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w) => //.
    + call (_ : size G3.cilog <= size G1.log /\ size G1.log <= PKE_.qD).
      + proc;auto => /#.
      auto => /= w /supp_dexcepted;smt (qD_pos).
    wp;conseq (_ : _ ==> G1.u \in map (fun (g4:ciphertext) => loge g4.`1) G3.cilog /\
                      G1.u' \in map (fun (g4:ciphertext) => loge g4.`2 / G1.w) G3.cilog /\
                      r' \in map (fun (g4:ciphertext) => loge g4.`3) G3.cilog /\
                      r \in map (fun (g4:ciphertext) => loge g4.`4) G3.cilog).
    + move=> &hr /> _ Hw u u' r r' Hlog.
      do !split;apply mapP;
       exists (g ^ u, g ^ G1.w{hr} ^ u', g ^ r', g ^ r);
       rewrite Hlog /= !logrzM ?logg1; 1, 3, 4: by ring.
       by field.
    seq 1 : (G1.u \in map (fun (g4 : ciphertext) => loge g4.`1) G3.cilog)
            (PKE_.qD%r / order%r) ((PKE_.qD%r / order%r)^2 * (PKE_.qD%r / (order - 1)%r))
            _ 0%r (size G3.cilog <= PKE_.qD) => //;
    last 2 first.
    + hoare;conseq (_ : _ ==> true) => // /#.
    + move=> &hr _;apply lerr_eq;ring.
    + by auto.
    + rnd;skip => /> &hr Hsize _;pose m' := map _ _.
      apply (mu_mem_le_mu1_size dt m') => //.
      + by rewrite /m' size_map.
      by move=> ?;rewrite dt1E.
    seq 1 : (G1.u' \in map (fun (g4 : ciphertext) => loge g4.`2 / G1.w) G3.cilog)
            (PKE_.qD%r / (order-1)%r) ((PKE_.qD%r / order%r)^2) _ 0%r
            (size G3.cilog <= PKE_.qD) => //;last 2 first.
    + hoare;conseq (_ : _ ==> true) => // /#.
    + move=> &hr _;apply lerr_eq;ring.
    + by auto.
    + rnd;skip => /> &hr Hsize _;pose m' := map _ _.
      apply (mu_mem_le_mu1_size (dt \ pred1 G1.u{hr}) m') => //.
      + by rewrite /m' size_map.
      move=> x;rewrite dexcepted1E {1}/pred1.
      case: (x = G1.u{hr}) => _.
      + apply invr_ge0;smt (le_fromint gt1_q).
      rewrite dt_ll !dt1E;apply lerr_eq.
      field;smt (gt1_q le_fromint).
    seq 1 : (r' \in map (fun (g4 : ciphertext) => loge g4.`3) G3.cilog)
            (PKE_.qD%r / order%r) (PKE_.qD%r / order%r) _ 0%r
            (size G3.cilog <= PKE_.qD) => //;last 2 first.
    + hoare;conseq (_ : _ ==> true) => // /#.
    + move=> &hr _;apply lerr_eq;field.
      + rewrite expr2; smt (gt1_q).
      + smt (gt1_q).
    + by auto.
    + rnd;skip => /> &hr Hsize _;pose m' := map _ _.
      apply (mu_mem_le_mu1_size dt m') => //.
      + by rewrite /m' size_map.
      by move=> ?;rewrite dt1E.
    conseq (_ : _ ==> (r \in map (fun (g4 : ciphertext) => loge g4.`4) G3.cilog)) => //.
    rnd;skip => /> &hr Hsize _;pose m' := map _ _.
    apply (mu_mem_le_mu1_size dt m') => //.
    + by rewrite /m' size_map.
    by move=> ?;rewrite dt1E.
  qed.

  lemma aux2 &m :
    Pr[CCA(CramerShoup, A).main() @ &m : res] <=
    `|Pr[DDH0(B_DDH(A)).main() @ &m : res] -
      Pr[DDH1(B_DDH(A)).main() @ &m : res]| +
    Pr[TCR(B_TCR(A)).main() @ &m : res] +
    1%r/2%r + (PKE_.qD + 3)%r / order%r + (PKE_.qD%r/order%r)^3 * (PKE_.qD%r/(order-1)%r).
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

end section Security_Aux.

section Security.

  declare module A <: CCA_ADV {-CCA, -B_TCR}.
  declare axiom guess_ll : forall (O <: CCA_ORC{-A}), islossless O.dec => islossless A(O).guess.
  declare axiom choose_ll : forall (O <: CCA_ORC{-A}), islossless O.dec => islossless A(O).choose.

  local module NA (O:CCA_ORC) = {
    module A = A(O)
    proc choose = A.choose
    proc guess(c:ciphertext) = {
      var b;
      b <@ A.guess(c);
      return !b;
    }
  }.

  local lemma CCA_NA &m :
     Pr[CCA(CramerShoup, A).main() @ &m : res] =
     1%r - Pr[CCA(CramerShoup, NA).main() @ &m : res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  local lemma DDH0_NA &m : Pr[DDH0(B_DDH(NA)).main() @ &m : res] =
                        1%r - Pr[DDH0(B_DDH(A)).main() @ &m : res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    have -> : Pr[DDH0(B_DDH(NA)).main() @ &m : res] =
              Pr[DDH0(B_DDH(A)).main() @ &m : !res].
    + byequiv => //; proc;
        inline B_DDH(NA).guess B_DDH(A).guess;
        inline{1} NA(CCA(CramerShoup, NA).O).guess.
      wp; call (_: ={B_DDH.CCA.log, B_DDH.CCA.cstar, B_DDH.CCA.sk}).
      + by proc; inline *; auto.
      wp; rnd; wp;
        call (_: ={B_DDH.CCA.log, B_DDH.CCA.cstar, B_DDH.CCA.sk}).
      + by proc; inline *; auto.
      by auto => /> /#.
    rewrite Pr[mu_not]; congr.
    byphoare => //; proc; call (_: true ==> true);
      last by auto; smt(dt_ll).
    proc; wp; call (: true).
    + by apply guess_ll.
    + by islossless.
    wp; rnd; wp; call (: true).
    + by apply choose_ll.
    + by islossless.
    islossless.
  qed.

  local lemma DDH1_NA &m : Pr[DDH1(B_DDH(NA)).main() @ &m : res] =
                        1%r - Pr[DDH1(B_DDH(A)).main() @ &m : res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  local lemma TCR_NA &m : Pr[TCR(B_TCR(NA)).main() @ &m : res] =
                          Pr[TCR(B_TCR(A)).main() @ &m : res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    byequiv => //; proc; inline B_TCR(NA).c2 B_TCR(A).c2;
      inline{1} NA(B_TCR(NA).O).guess; wp;
      call (_: ={glob B_TCR}); [by proc; auto |
      wp; call (_: ={glob B_TCR}); [by proc; auto |
      inline B_TCR(NA).c1 B_TCR(A).c1; do 7!(wp; rnd); auto; smt()]].
  qed.

  lemma conclusion &m :
    `|Pr[CCA(CramerShoup, A).main() @ &m : res] - 1%r/2%r | <=
    `|Pr[DDH0(B_DDH(A)).main() @ &m : res] - Pr[DDH1(B_DDH(A)).main() @ &m : res]| +
    Pr[TCR(B_TCR(A)).main() @ &m : res] +
    (PKE_.qD + 3)%r / order%r + (PKE_.qD%r/order%r)^3 * (PKE_.qD%r/(order-1)%r).
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

end section Security.