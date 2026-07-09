require import AllCore Int Real FSet StdOrder.
require (*--*) BitWord Distr DInterval.
(*---*) import RealOrder RField.
require (*--*) DiffieHellman ROM PKE_CPA.

(* The type of plaintexts: bitstrings of length k *)
op k: { int | 0 < k } as gt0_k.

clone import BitWord as Bits with
  op n <- k
proof gt0_n by exact/gt0_k
rename
  "word" as "bits"
  "dunifin" as "dbits".
import DWord.

(* Upper bound on the number of calls to H *)
op qH: { int | 0 < qH } as gt0_qH.

(* Assumption: Set CDH *)
clone import DiffieHellman.Set_CDH as SCDH with
  op n <- qH.

import DiffieHellman.
import G GP GP.ZModE FD.

type pkey = group.
type skey = exp.
type ptxt = bits.
type ctxt = group * bits.

(* Goal: PK IND-CPA *)
clone import PKE_CPA as PKE with
  type pkey <- pkey,
  type skey <- skey,
  type ptxt <- ptxt,
  type ctxt <- ctxt.

(* Some abstract hash oracle *)
module type Hash = {
  proc init(): unit
  proc hash(x:group): bits
}.

module Hashed_ElGamal (H:Hash): Scheme = {
  proc kg(): pkey * skey = {
    var sk;

    H.init();
    sk <$ dt;
    return (g ^ sk, sk);
  }

  proc enc(pk:pkey, m:ptxt): ctxt = {
    var y, h;

    y <$ dt;
    h <@ H.hash(pk ^ y);
    return (g ^ y, h +^ m);
  }

  proc dec(sk:skey, c:ctxt): ptxt option = {
    var gy, h, hm;

    (gy, hm) <- c;
    h        <@ H.hash(gy ^ sk);
    return Some (h +^ hm);
  }
}.

clone import ROM as RO with
  type in_t    <- group,
  type out_t   <- bits,
  type d_in_t  <- unit,
  type d_out_t <- bool,
  op   dout _  <- dbits.
import Lazy.
clone import ROM_BadCall as ROC with
  op qH <- qH.

(* Adversary Definitions *)
module type Adversary (O : POracle) = {
  proc choose(pk:pkey): ptxt * ptxt
  proc guess(c:ctxt)  : bool
}.

(* Specializing and merging the hash function *)
module H : Hash = {
  proc init(): unit = { LRO.init(); Log.qs <- fset0; }
  proc hash(x:group): bits = { var y; y <@ LRO.o(x); return y; }
}.

(* The initial scheme *)
module S = Hashed_ElGamal(H).

(* The reduction *)
module SCDH_from_CPA(A:Adversary,O:Oracle): Top.SCDH.Adversary = {
  module BA = A(Bound(O))

  proc solve(gx:group, gy:group): group fset = {
    var m0, m1, h, b';

    H.init();
    (m0,m1)  <@ BA.choose(gx);
    h        <$ dbits;
    b'       <@ BA.guess(gy, h);
    return Log.qs;
  }
}.

(* We want to bound the probability of A winning CPA(Bounder(A,RO),S) in terms of
   the probability of B = CDH_from_CPA(SCDH_from_CPA(A,RO)) winning CDH(B) *)
section.
  declare module A <: Adversary { -LRO, -Log, -OnBound.G1, -OnBound.G_bad }.

  declare axiom choose_ll (O <: POracle {-A}): islossless O.o => islossless A(O).choose.
  declare axiom guess_ll (O <: POracle {-A}) : islossless O.o => islossless A(O).guess.

  local module BA = A(Bound(LRO)).

  local module G0 = {
    var gxy:group

    proc main(): bool = {
      var m0, m1, c, b, b';
      var x, y, h, gx;

      H.init();
      x       <$ dt;
      y       <$ dt;
      gx      <- g ^ x;
      gxy     <- gx ^ y;
      (m0,m1) <@ BA.choose(gx);
      b       <$ {0,1};
      h       <@ H.hash(gxy);
      c       <- (g ^ y, h +^ (b ? m1 : m0));
      b'      <@ BA.guess(c);
      return (b' = b);
    }
  }.

  local equiv CPA_G0: CPA(S,BA).main ~ G0.main: ={glob A} ==> ={res}.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    (* byequiv with inline; complex swap alignment needed *)
    admit.
  qed.

  local lemma Pr_CPA_G0 &m:
    Pr[CPA(S,BA).main() @ &m: res] = Pr[G0.main() @ &m: res]
  by byequiv CPA_G0.

  local module G1 = {
    proc main() : bool = {
      var m0, m1, c, b, b';
      var x, y, h, gx, gxy;

      H.init();
      x       <$ dt;
      y       <$ dt;
      gx      <- g ^ x;
      gxy     <- gx ^ y;
      (m0,m1) <@ BA.choose(gx);
      b       <$ {0,1};
      h       <$ dbits;
      c       <- (g ^ y, h +^ (b ? m1 : m0));
      b'      <@ BA.guess(c);
      return (b' = b);
    }
  }.

  local module G2 = {
    var gxy : group

    proc main() : bool = {
      var m0, m1, c, b, b';
      var x, y, h, gx;

      H.init();
      x       <$ dt;
      y       <$ dt;
      gx      <- g ^ x;
      gxy     <- gx ^ y;
      (m0,m1) <@ BA.choose(gx);
      b       <$ {0,1};
      h       <$ dbits;
      c       <- (g ^ y, h +^ (b ? m1 : m0));
      b'      <@ BA.guess(c);
      return G2.gxy \in Log.qs;
    }
  }.

  local module (D : ROC.Dist) (H : POracle) = {
    module A = A(H)

    var y:exp
    var b:bool
    var m0, m1:ptxt

    proc a1(): group = {
      var x, gxy, gx;

      x       <$ dt;
      y       <$ dt;
      gx      <- g ^ x;
      gxy     <- gx ^ y;
      (m0,m1) <@ A.choose(gx);
      b       <$ {0,1};
      return gxy;
    }

    proc a2(x:bits): bool = {
      var c, b';

      c  <- (g ^ y, x +^ (b ? m1 : m0));
      b' <@ A.guess(c);
      return (b' = b);
    }
  }.

  local lemma G0_D &m: Pr[G0.main() @ &m: res] = Pr[OnBound.G0(D,LRO).main() @ &m: res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    byequiv=> //; proc; inline *; wp; sim.
  qed.

  local lemma G1_D &m: Pr[G1.main() @ &m: res] = Pr[OnBound.G1(D,LRO).main() @ &m: res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    byequiv=> //; proc; inline *; wp; sim.
  qed.

  local lemma G2_D &m: Pr[G2.main() @ &m: res] = Pr[OnBound.G_bad(D,LRO).main() @ &m: res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    byequiv=> //; proc; inline *; wp; sim.
  qed.

  local lemma G0_G1_G2 &m:
    Pr[G0.main() @ &m: res] <= Pr[G1.main() @ &m: res] + Pr[G2.main() @ &m: res].
  proof.
  rewrite (G0_D &m) (G1_D &m) (G2_D &m).
  move: (OnBound.ROM_BadCall D _ _ _ &m tt true).
  + move=> H H_o_ll; proc; auto; call (choose_ll H _)=> //; auto=> />.
    by rewrite dt_ll DBool.dbool_ll.
  + by move=> H H_o_ll; proc; auto; call (guess_ll H _)=> //; auto=> />.
  + by move=> _; apply: dbits_ll.
  apply iffLR.
  congr; 2:congr.
  + byequiv (: ={glob OnBound.G0(D, LRO), arg} ==>
               ={glob OnBound.G0(D, LRO), res}) => />; 1:sim.
  byequiv (: ={glob OnBound.G1(D, LRO), arg} ==>
             ={glob OnBound.G1(D, LRO), res}) => />; 1:sim.
  qed.

  local module G1' = {
    proc main() : bool = {
      var m0, m1, c, b, b';
      var x, y, h, gx, gxy;

      H.init();
      x       <$ dt;
      y       <$ dt;
      gx      <- g ^ x;
      gxy     <- gx ^ y;
      (m0,m1) <@ BA.choose(gx);
      b       <$ {0,1};
      h       <$ dbits;
      c       <- (g ^ y, h);
      b'      <@ BA.guess(c);
      return (b' = b);
    }
  }.

  local lemma G1_G1' &m: Pr[G1.main() @ &m: res] = Pr[G1'.main() @ &m: res].
  proof.
    byequiv (_: ={glob A} ==> ={res})=> //.
    proc.
    call (_: ={glob LRO, glob Log}); first by sim.
    wp; rnd (fun h, h +^ if b then m1 else m0){1}; rnd.
    call (_: ={glob LRO, glob Log}); first by sim.
    by inline H.init LRO.init; auto=> /> *; split => *; algebra.
  qed.

  local lemma Pr_G1' &m: Pr[G1'.main() @ &m: res] = 1%r/2%r.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    (* guessing game: b independent of b'; byphoare + rnd (pred1 b') *)
    admit.
  qed.

  local module G2' = {
    var gxy : group

    proc main() : bool = {
      var m0, m1, c, b, b';
      var x, y, h, gx;

      H.init();
      x        <$ dt;
      y        <$ dt;
      gx       <- g ^ x;
      gxy      <- gx ^ y;
      (m0,m1)  <@ BA.choose(gx);
      b        <$ {0,1};
      h        <$ dbits;
      c        <- (g ^ y, h);
      b'       <@ BA.guess(c);
      return gxy \in Log.qs;
    }
  }.

  local lemma G2_G2' &m: Pr[G2.main() @ &m: res] = Pr[G2'.main() @ &m: res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    (* OTP argument similar to G1_G1' *)
    admit.
  qed.

  local equiv G2'_SCDH: G2'.main ~ SCDH(SCDH_from_CPA(A,LRO)).main:
    ={glob A} ==> res{1} = res{2} /\ card Log.qs{1} <= qH.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    (* reduction equiv to SCDH *)
    admit.
  qed.

  local lemma Pr_G2'_SCDH &m :
    Pr[G2'.main() @ &m: res]
    = Pr[SCDH(SCDH_from_CPA(A,LRO)).main() @ &m : res]
  by byequiv G2'_SCDH.

  local lemma Reduction &m :
    Pr[CPA(S,BA).main() @ &m : res] <=
    1%r / 2%r + Pr[SCDH(SCDH_from_CPA(A,LRO)).main() @ &m : res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    have h0 := Pr_CPA_G0 &m.
    have h1 := G0_G1_G2 &m.
    have h2 := G1_G1' &m.
    have h3 := Pr_G1' &m.
    have h4 := G2_G2' &m.
    have h5 := Pr_G2'_SCDH &m.
    smt().
  qed.

  (** Composing reduction from CPA to SCDH with reduction from SCDH to CDH *)

  lemma Security &m:
      Pr[CPA(S,A(Bound(LRO))).main() @ &m: res] - 1%r / 2%r <=
      qH%r * Pr[CDH.CDH(CDH_from_SCDH(SCDH_from_CPA(A,LRO))).main() @ &m: res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    (* combine Reduction with SCDH.Reduction *)
    admit.
  qed.
end section.

print axiom Security.
