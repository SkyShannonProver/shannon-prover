require import AllCore Distr List Real FMap FSet DInterval FinType KEM_ROM.

require   PKE_ROM PlugAndPray Hybrid FelTactic.

require FO_TT.

clone import FO_TT as TT.

import PKE.

type key.

op [lossless uniform full]dkey : key distr.

require PRF.

clone import PRF as J with
   type D <- ciphertext,
   type R <- key.

clone import RF with
   op dR <- fun _ => dkey
   proof dR_ll by (move => *;apply dkey_ll)
   proof *.

clone import PseudoRF.

clone import KEM_ROM.KEM_ROM_x2 as KEMROMx2 with
   type pkey <- pkey,
   type skey = (pkey * skey) * K,
   type ciphertext <- ciphertext,
   type key <- key,
   op dkey <- dkey,
   type RO1.in_t <- plaintext,
   type RO1.out_t <- randomness,
   op   RO1.dout <- fun _ => randd,
   type RO1.d_in_t <- unit,
   type RO1.d_out_t <- bool,
   type RO2.in_t <- plaintext,
   type RO2.out_t <- key,
   op   RO2.dout <- fun _ => dkey,
   type RO2.d_in_t <- unit,
   type RO2.d_out_t <- bool
   proof dkey_ll by apply dkey_ll
   proof dkey_uni by apply dkey_uni
   proof dkey_fu by apply dkey_fu
   proof *.

const qHT : { int | 0 <= qHT } as ge0_qHT.

const qHU : { int | 0 <= qHU } as ge0_qHU.

const qD : { int | 0 <= qD } as ge0_qD.

module (UU : KEMROMx2.Scheme) (H : POracle_x2) = {

  module HT : PKEROM.POracle = {
     proc get = H.get1
  }

  module HU = {
     proc get = H.get2
  }

  proc kg() : pkey * skey = {
     var pk, sk, k;
     (pk,sk) <$ kg;
     k <$ dK;
     return (pk, ((pk,sk),k));
  }

  proc enc(pk : pkey) : ciphertext * key = {
     var m, c, k;
     m <$ dplaintext;
     c <@TT(HT).enc(pk,m);
     k <@ HU.get(m);
     return (c,k);
  }

  proc dec(sk : skey, c : ciphertext) : key option = {
     var m', k;
     k <- witness;
     m' <@ TT(HT).dec(sk.`1,c);
     if (m' = None) {
        k <- F sk.`2 c;
     }
     else {
        k <@ HU.get(oget m');
     }
     return (Some k);
  }
}.

module (B_UC : PKEROM.CORR_ADV)  (HT : PKEROM.POracle)= {
   proc find(pk : pkey, sk : PKEROM.skey) : plaintext = {
      var m;
      m <$ dplaintext;
      return m;
   }
}.

module CountHx2(H : KEMROMx2.POracle_x2) = {
  var c_hu   : int
  var c_ht   : int

  proc init () = { c_ht <- 0; c_hu <- 0;   }

  proc get1(x:plaintext) = {
    var r;
    r <@ H.get1(x);
    c_ht <- c_ht + 1;
    return r;
  }
  proc get2(x:plaintext) = {
    var r;
    r <@ H.get2(x);
    c_hu <- c_hu + 1;
    return r;
  }
}.

module (UU1(PRFO : PRF_Oracles) : KEMROMx2.Scheme) (H : POracle_x2) = {
  include UU(H) [-kg,dec]

  proc kg() : pkey * skey = {
     var pk, sk;
     (pk,sk) <$ kg;
     return (pk, ((pk,sk),witness));
  }

  proc dec(sk : skey, c : ciphertext) : key option = {
     var m', k;
     k <- witness;
     m' <@ TT(UU(H).HT).dec(sk.`1,c);
     if (m' = None) {
        k <@ PRFO.f(c);
     }
     else {
        k <@ UU(H).HU.get(oget m');
     }
     return (Some k);
  }
}.

module Gm1P(H : Oracle_x2, A : CCA_ADV, PRFO : PRF_Oracles) = {

  proc main'() : bool = {
    var pk : pkey;
    var k1 : key;
    var ck0 : ciphertext * key;
    var b : bool;
    var b' : bool;

    H.init();
    CCA.cstar <- None;
    (pk, CCA.sk) <@ UU1(PRFO,H).kg();
    k1 <$ dkey;
    b <$ {0,1};
    ck0 <@ UU1(PRFO,H).enc(pk);
    CCA.cstar <- Some ck0.`1;
    b' <@ CCA(H, UU1(PRFO),A).A.guess(pk, ck0.`1, if b then k1 else ck0.`2);

    return b' = b;
  }
}.

module Gm1(H : Oracle_x2, A : CCA_ADV) = {
    proc main() : bool = {
       var b;
       RF.init();
       b <@ Gm1P(H,A,RF).main'();
       return b;
    }
}.

module D(A : CCA_ADV, PRFO : PRF_Oracles) = {
   proc distinguish = Gm1P(RO_x2(RO1.RO,RO2.RO),A,PRFO).main'
}.

clone import KEMROMx2.RO1.FinEager as RO1E
   with op FinFrom.enum = FinT.enum
   proof FinFrom.enum_spec by apply FinT.enum_spec
   proof *.

module RO_x2E = RO_x2(RO1E.FunRO,RO2.RO).

module (UU2 : KEMROMx2.Scheme) (H : POracle_x2) = {
  include UU1(RF,H) [-dec]

  var lD : (ciphertext * key) list

  proc dec(sk : skey, c : ciphertext) : key option = {
     var k, ko;
     ko <- None;
     if (assoc lD c <> None) {
        ko <- assoc lD c;
     }
     else {
        k <$ dkey;
        ko <- Some k;



        lD <- (c,k) :: lD;
     }
     return ko;
  }
}.

module H1 : POracle_x2 = {
     var bad : bool

     proc init() = {}
     proc get1 = RO_x2E.get1
     proc get2(m : plaintext) : key = {
       var k,cm;
       cm <- enc (RO1E.FunRO.f m) CCA.sk.`1.`1 m;
       bad <- if dec CCA.sk.`1.`2 cm <> Some m then true else bad;
       k <$ dkey;
       if (m \notin RO2.RO.m) {
         RO2.RO.m.[m] <- k;
       }
       return oget RO2.RO.m.[m];
     }
  }.

module H2(O1 : PKEROM.POracle) : POracle_x2 = {
     var merr : plaintext option
     var invert : bool
     var mtgt : plaintext

     proc init() = {}
     proc get1 = RO_x2E.get1
     proc get2(m : plaintext) : key = {
       var k,cm,r;
       mtgt <- if CCA.cstar = None then m else mtgt;
       r <@ O1.get(m);
       cm <- enc r CCA.sk.`1.`1 m;


       H1.bad <- if dec CCA.sk.`1.`2 cm <> Some m then true else H1.bad;
       H2.merr <- if H2.merr = None && H1.bad then Some m else H2.merr;
       H2.invert <- if CCA.cstar <> None && m = mtgt &&
                       dec CCA.sk.`1.`2 (oget CCA.cstar) = Some mtgt
                    then true else H2.invert;
       k <$ dkey;
       if (m \notin RO2.RO.m) {
         if (assoc UU2.lD cm <> None) {
             k <- oget (assoc UU2.lD cm);
         }
         else {
             UU2.lD <- if H1.bad then UU2.lD else (cm,k) :: UU2.lD;
         }
         RO2.RO.m <- if H1.bad then RO2.RO.m else RO2.RO.m.[m <- k];
       }
       return if H1.bad then witness else oget (RO2.RO.m.[m]);
     }
  }.

module Gm2(H : Oracle_x2, S : KEMROMx2.Scheme, A : CCA_ADV) = {

  module O = {
    proc dec(c : ciphertext) : key option = {
      var k : key option;

      k <- None;
      if (Some c <> CCA.cstar)
        k <@ S(H).dec(CCA.sk, c);

      return k;
    }
  }

  proc main2() : bool = {
    var pk : pkey;
    var k1 : key;
    var ck0 : ciphertext * key;
    var cstar : ciphertext option;
    var b : bool;
    var b' : bool;

    H1.bad <- false;
    H2.merr <- None;
    H2.invert <- false;
    RF.init();
    RO_x2E.init();
    UU2.lD <- [];
    CCA.cstar <- None;
    (pk, CCA.sk) <@ S(H).kg();
    k1 <$ dkey;
    b <$ {0,1};
    ck0 <@ UU2(H).enc(pk);
    CCA.cstar <- Some ck0.`1;
    b' <@ CCA(H, S, A).A.guess(pk, ck0.`1, if b then k1 else ck0.`2);
    return b' = b;
  }

  proc main() : bool = {
    var win,nobias;
    win <@ main2();
    nobias <$ {0,1};
    return (if H1.bad then nobias else win);
  }

}.

module (BUUC(A : CCA_ADV) : PKEROM.CORR_ADV) (H : PKEROM.POracle) = {

   module H2B = {
      include H2(H) [-get1]
      proc get1= H.get
   }

   proc find(pk : pkey, sk : PKEROM.skey) : plaintext = {
    var k1 : key;
    var ck0 : ciphertext * key;
    var cstar : ciphertext option;
    var b : bool;
    var b' : bool;
    var z : K;

    H1.bad <- false;
    H2.merr <- None;
    H2.invert <- false;
    RF.init();
    RO2.RO.init();
    UU2.lD <- [];
    CCA.cstar <- None;
    CCA.sk <- (sk,witness);
    k1 <$ dkey;
    b <$ {0,1};
    ck0 <@ UU2(H2B).enc(pk);
    CCA.cstar <- Some ck0.`1;
    CountHx2(H2B).init();
    b' <@ CCA(CountHx2(H2B), UU2, A).A.guess(pk, ck0.`1, if b then k1 else ck0.`2);
    return (oget H2.merr);
   }
}.

module Gm3(H : Oracle_x2, S : KEMROMx2.Scheme, A : CCA_ADV) = {
  module O = {
    proc dec(c : ciphertext) : key option = {
      var k : key option;

      k <- None;
      if (Some c <> CCA.cstar)
        k <@ S(H).dec(CCA.sk, c);

      return k;
    }
  }

  proc main() : bool = {
    var pk : pkey;
    var k1, k2 : key;
    var b : bool;
    var b' : bool;
    var r : randomness;
    var cm : ciphertext;
    var nobias : bool;

    H1.bad <- false;
    H2.merr <- None;
    H2.invert <- false;
    RF.init();
    RO_x2E.init();
    UU2.lD <- [];
    CCA.cstar <- None;
    (pk, CCA.sk) <@ S(H).kg();
    k1 <$ dkey; k2 <$ dkey;
    b <$ {0,1};
    H2.mtgt <$ dplaintext;

    r <@ H.get1(H2.mtgt);
    cm <- enc r pk H2.mtgt;
    H1.bad <- if dec CCA.sk.`1.`2 cm <> Some H2.mtgt then true else H1.bad;
    H2.merr <- if H2.merr = None && H1.bad then Some H2.mtgt else H2.merr;
    UU2.lD <- (cm,witness) :: UU2.lD;
    CCA.cstar <- Some cm;
    b' <@ CCA(H, S, A).A.guess(pk, cm, if b then k1 else k2);
    nobias <$ {0,1};
    return (if H1.bad then nobias else (b' = b));
  }

  proc main_0adv() : bool = {
    var pk : pkey;
    var k : key;
    var b : bool;
    var b' : bool;
    var r : randomness;
    var cm : ciphertext;
    var nobias : bool;

    H1.bad <- false;
    H2.merr <- None;
    H2.invert <- false;
    RF.init();
    RO_x2E.init();
    UU2.lD <- [];
    CCA.cstar <- None;
    (pk, CCA.sk) <@ S(H).kg();
    k <$ dkey;
    H2.mtgt <$ dplaintext;

    r <@ H.get1(H2.mtgt);
    cm <- enc r pk H2.mtgt;
    H1.bad <- if dec CCA.sk.`1.`2 cm <> Some H2.mtgt then true else H1.bad;
    H2.merr <- if H2.merr = None && H1.bad then Some H2.mtgt else H2.merr;
    UU2.lD <- (cm,witness) :: UU2.lD;
    CCA.cstar <- Some cm;
    b' <@ CCA(H, S, A).A.guess(pk, cm, k);
    nobias <$ {0,1};
    b <$ {0,1};
    return (if H1.bad then nobias else (b' = b));
  }

}.

module H2BOW(OO1 : PKEROM.POracle) : POracle_x2 = {
     proc init() = {}
     proc get1 = RO_x2E.get1
     proc get2(m : plaintext) : key = {
       var k,cm, r;
       r <@ OO1.get(m);
       cm <- enc r CCA.sk.`1.`1 m;
       H1.bad <- if dec CCA.sk.`1.`2 cm <> Some m then true else H1.bad;
       H2.merr <- if H2.merr = None && H1.bad then Some m else H2.merr;
       H2.invert <- if CCA.cstar <> None &&  m = H2.mtgt &&
                       dec CCA.sk.`1.`2 (oget CCA.cstar) = Some H2.mtgt
                    then true else H2.invert;
       k <$ dkey;
       if (m \notin RO2.RO.m) {
         if (assoc UU2.lD cm <> None) {
             k <- oget (assoc UU2.lD cm);
         }
         else {
             UU2.lD <- (cm,k) :: UU2.lD;
         }
         RO2.RO.m <- RO2.RO.m.[m <- k];
       }
       return  oget (RO2.RO.m.[m]);
     }
  }.

module (BUUOW(A : CCA_ADV) : PKEROM.PCVA_ADV) (H : PKEROM.POracle, O : PKEROM.VA_ORC) = {

   module H2B = {
      include H2BOW(H) [-get1]
      proc get1= H.get
   }

   proc find(pk : pkey, cm : ciphertext) : plaintext option = {
    var k1, k2 : key;
    var b : bool;
    var b' : bool;
    var r : randomness;

    H1.bad <- false;
    H2.merr <- None;
    H2.invert <- false;
    RF.init();
    RO2.RO.init();
    UU2.lD <- [];
    CCA.cstar <- None;
    CCA.sk <- ((pk,witness),witness);
    k1 <$ dkey; k2 <$ dkey;
    b <$ {0,1};
    UU2.lD <- (cm,witness) :: UU2.lD;
    CCA.cstar <- Some cm;
    b' <@ CCA(H2B, UU2, A).A.guess(pk, cm, if b then k1 else k2);
    return if card (filter (fun m0 => enc (FunRO.f m0) pk m0 =
                 oget CCA.cstar)  (fdom RO2.RO.m)) = 1 then
        Some (head witness (elems (filter (fun m0 => enc (FunRO.f m0) pk m0 =
                 oget CCA.cstar) (fdom RO2.RO.m)))) else None;
   }

}.

module H2BOWMod(OO1 : PKEROM.POracle) : POracle_x2 = {
    var crd : int
    var mf : plaintext option

     proc init() = {}
     proc get1 = RO_x2E.get1
     proc get2(m : plaintext) : key = {
       var k,cm, r;
       r <@ OO1.get(m);
       cm <- enc r CCA.sk.`1.`1 m;
       H1.bad <- if dec CCA.sk.`1.`2 cm <> Some m then true else H1.bad;
       H2.merr <- if H2.merr = None && H1.bad then Some m else H2.merr;
       H2.invert <- if CCA.cstar <> None &&  m = H2.mtgt &&
                       dec CCA.sk.`1.`2 (oget CCA.cstar) = Some H2.mtgt
                    then true else H2.invert;
       k <$ dkey;
       if (m \notin RO2.RO.m) {
         crd <- crd + b2i (Some cm = CCA.cstar);
         mf <- if Some cm = CCA.cstar then Some m else mf;

         if (assoc UU2.lD cm <> None) {
             k <- oget (assoc UU2.lD cm);
         }
         else {
             UU2.lD <- (cm,k) :: UU2.lD;
         }
         RO2.RO.m <- RO2.RO.m.[m <- k];
       }
       return  oget (RO2.RO.m.[m]);
     }
  }.

module (BUUOWMod(A : CCA_ADV) : PKEROM.PCVA_ADV) (H : PKEROM.POracle, O : PKEROM.VA_ORC) = {

   module H2B = {
      include H2BOWMod(H) [-get1]
      proc get1= H.get
   }

   proc find(pk : pkey, cm : ciphertext) : plaintext option = {
    var k1, k2 : key;
    var b : bool;
    var b' : bool;

    H1.bad <- false;
    H2.merr <- None;
    H2.invert <- false;
    RF.init();
    RO2.RO.init();
    UU2.lD <- [];
    CCA.cstar <- None;
    CCA.sk <- ((pk,witness),witness);
    k1 <$ dkey; k2 <$ dkey;
    b <$ {0,1};
    UU2.lD <- (cm,witness) :: UU2.lD;
    CCA.cstar <- Some cm;
    H2BOWMod.crd <- 0;
    H2BOWMod.mf <- None;
    CountHx2(H2B).init();
    b' <@ CCA(CountHx2(H2B), UU2, A).A.guess(pk, cm, if b then k1 else k2);
    return if H2BOWMod.crd = 1 then  H2BOWMod.mf else None;
   }

}.

module (BUUCI(A : CCA_ADV) : PKEROM.CORR_ADV) (H : PKEROM.POracle) = {

   module H2B = {
      include H2(H) [-get1]
      proc get1= H.get
   }

   proc find(pk : pkey, sk : PKEROM.skey) : plaintext = {
    var k1, k2 : key;
    var b : bool;
    var b' : bool;
    var r : randomness;
    var cm : ciphertext;
    var nobias : bool;

    H1.bad <- false;
    H2.merr <- None;
    H2.invert <- false;
    RF.init();
    RO2.RO.init();
    UU2.lD <- [];
    CCA.cstar <- None;
    CCA.sk <- (sk,witness);
    k1 <$ dkey; k2 <$ dkey;
    b <$ {0,1};
    H2.mtgt <$ dplaintext;

    r <@ H2B.get1(H2.mtgt);
    cm <- enc r pk H2.mtgt;
    H1.bad <- if dec CCA.sk.`1.`2 cm <> Some H2.mtgt then true else H1.bad;
    H2.merr <- if H2.merr = None && H1.bad then Some H2.mtgt else H2.merr;
    UU2.lD <- (cm,witness) :: UU2.lD;
    CCA.cstar <- Some cm;
    CountHx2(H2B).init();
    b' <@ CCA(CountHx2(H2B), UU2, A).A.guess(pk, cm, if b then k1 else k2);
    return (oget H2.merr);
   }
}.

op c2m(c : ciphertext, sk : PKEROM.skey) : plaintext option = dec sk.`2 c.

op oc2m(c : ciphertext, sk : PKEROM.skey) : plaintext = oget (dec sk.`2 c).

op m2c(m : plaintext, sk : PKEROM.skey, f : plaintext -> randomness) : ciphertext = enc (f m) sk.`1 m.

op goodc(c : ciphertext, sk : PKEROM.skey, f : plaintext -> randomness) =
          c2m c sk <> None /\ m2c (oc2m c sk) sk f = c.
