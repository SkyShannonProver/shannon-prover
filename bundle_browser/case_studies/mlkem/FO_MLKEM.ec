require import AllCore Distr List Real FMap FSet DInterval FinType KEM_ROM.

require   PKE_ROM PlugAndPray Hybrid FelTactic.

require FO_UU.

clone import FO_UU as UU.

import KEMROMx2.

import TT.

import PKE.

import PseudoRF.

import RF.

type pkhash.

op pkh : pkey -> pkhash.

clone import KEM_ROM.KEM_ROM as KEMROM with
   type pkey <- pkey,
   type skey = (pkey * skey) * K,
   type ciphertext <- ciphertext,
   type key <- key,
   op dkey <- dkey,
   type RO.in_t <- plaintext * pkhash,
   type RO.out_t <- key * randomness,
   op   RO.dout <- fun _ => dkey `*` randd,
   type RO.d_in_t <- unit,
   type RO.d_out_t <- bool.

const qHK : { int | 0 <= qHK } as ge0_qHK.

module CountH(H : POracle) = {
  var c_h   : int

  proc init () = { c_h <- 0;  }

  proc get(x: plaintext * pkhash) = {
    var r;
    r <@ H.get(x);
    c_h <- c_h + 1;
    return r;
  }
}.

module (FO_K : KEMROM.Scheme) (H : POracle) = {

  proc kg() : pkey * skey = {
     var pk, sk, k;
     (pk,sk) <$ kg;
     k <$ dK;
     return (pk, ((pk,sk),k));
  }

  proc enc(pk : pkey) : ciphertext * key = {
     var m, r, c, k;
     m <$ dplaintext;
     (k,r) <@ H.get(m, pkh pk);
     c <- enc r pk m;
     return (c,k);
  }

  proc dec(sk : skey, c : ciphertext) : key option = {
     var m', c', ks, r, kn;
     m' <- dec sk.`1.`2 c;
     (ks,r) <@ H.get(oget m',pkh sk.`1.`1);
     kn <- F sk.`2 c;
     c' <- enc r sk.`1.`1 (oget m');
     return if (m' <> None /\ c' = c) then (Some ks) else (Some kn);
  }
}.

module UU_L(H1 : RO1.RO, H2 : RO2.RO) = {
  include UU(RO_x2(H1,H2)) [kg, enc]
  proc dec(sk : skey, c : ciphertext) : key option = {
    var m' : plaintext option;
    var r : randomness;
    var c' : ciphertext;
    var rv : plaintext option;
    var k : key;

    rv <- None;
    m' <- dec sk.`1.`2 c;
    H1.sample(oget m');
    H2.sample(oget m');
    if (m' <> None) {
      r <@ H1.get(oget m');
      c' <- enc r sk.`1.`1 (oget m');
      rv <- if c = c' then m' else None;
    }
    if (rv = None)
      k <- F sk.`2 c;
    else
      k <@ H2.get(oget m');

    return Some k;
   }
}.

module Correctness_L(H1 : RO1.RO, H2 : RO2.RO) = {
  proc main() : bool = {
    var pk : pkey;
    var sk : KEMROMx2.skey;
    var c : ciphertext;
    var k : key;
    var k' : key option;

    H1.init();
    H2.init();
    (pk, sk) <@ UU_L(H1,H2).kg();
    (c, k) <@ UU_L(H1,H2).enc(pk);
    k' <@ UU_L(H1,H2).dec(sk, c);

    return k' <> Some k;
  }
}.

module (DC1 : KEMROMx2.RO1.RO_Distinguisher) (G1 : RO1.RO) = {
   proc distinguish = Correctness_L(G1, RO2.LRO).main
}.

module (DC2 : KEMROMx2.RO2.RO_Distinguisher) (G2 : RO2.RO) = {
   proc distinguish = Correctness_L(RO1.RO, G2).main
}.

module CCAL(H1 : RO1.RO, H2 : RO2.RO, A : KEMROMx2.CCA_ADV) = {
  module O = {
    proc dec(c : ciphertext) : key option = {
      var k : key option;

      k <- None;
      if (Some c <> CCA.cstar)
        k <@ UU_L(H1,H2).dec(CCA.sk, c);

      return k;
    }
  }

  module A = A(RO_x2(H1,H2),O)

  proc main() : bool = {
    var pk : pkey;
    var k1 : key;
    var ck0 : ciphertext * key;
    var b : bool;
    var b' : bool;

    H1.init();
    H2.init();
    CCA.cstar <- None;
    (pk, CCA.sk) <@ UU_L(H1,H2).kg();
    k1 <$ dkey;
    b <$ {0,1};
    ck0 <@ UU_L(H1,H2).enc(pk);
    CCA.cstar <- Some ck0.`1;
    b' <@ A.guess(pk, ck0.`1, if b then k1 else ck0.`2);

    return b' = b;
  }
}.

module (B1x2(A : KEMROM.CCA_ADV) : KEMROMx2.CCA_ADV) (H2x : KEMROMx2.POracle_x2, DO : CCA_ORC)  = {
   var _pk : pkey
   module BH = {
      proc get(m : plaintext, hpk : pkhash) = {
         var r,k;
         (k,r) <@ RO.RO.get(m,hpk);
         if (hpk = pkh _pk) {
            r <@ H2x.get1(m);
            k <@ H2x.get2(m);
         }
         return (k,r);
      }
   }

   proc guess(pk : pkey, c : ciphertext, k : key) : bool = {
     var b;
     _pk <- pk;
     CountH(RO.RO).init();
     RO.RO.init();
     b <@ A(CountH(BH),DO).guess(pk,c,k);
     return b;
   }
}.

module (DKK1(A : KEMROMx2.CCA_ADV) : KEMROMx2.RO1.RO_Distinguisher) (G1 : RO1.RO) = {
   proc distinguish = CCAL(G1, RO2.LRO, A).main
}.

module (DKK2(A : KEMROMx2.CCA_ADV) : KEMROMx2.RO2.RO_Distinguisher) (G2 : RO2.RO) = {
   proc distinguish = CCAL(RO1.RO, G2, A).main
}.
