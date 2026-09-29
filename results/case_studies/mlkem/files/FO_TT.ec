require import AllCore Distr List Real FMap FSet DInterval.

require   FinType PKE_ROM PlugAndPray Hybrid FelTactic.

op find ['a, 'b] (f: 'a -> 'b -> bool) (m:('a, 'b) fmap) : ('a * 'b) option =
  let bindings = map (fun a => (a, oget m.[a])) (elems (fdom m)) in
  let n = find (fun (p: _ * _) => f p.`1 p.`2) bindings in
  if n < size bindings then Some (nth witness bindings n)
  else None.

type plaintext.

op [full lossless uniform]dplaintext : plaintext distr.

clone import FinType.FinType as FinT with
   type t <- plaintext.

type randomness.

op [lossless] randd : randomness distr.

clone import PKE_ROM.PKE as PKE with
  type plaintext <- plaintext,
  op dplaintext <- dplaintext,
  op MFinT.enum <- FinT.enum
  proof MFinT.enum_spec by apply FinT.enum_spec
  proof dplaintext_ll by apply dplaintext_ll
  proof dplaintext_uni by apply dplaintext_uni
  proof dplaintext_fu by apply dplaintext_fu
  proof *.

op [lossless] kg : (pkey * skey) distr.

op enc : randomness -> pkey -> plaintext -> ciphertext.

op dec : skey -> ciphertext -> plaintext option.

module BasePKE : PKE.Scheme = {
  proc kg() : pkey * skey = {
     var kpair;
     kpair <$ kg;
     return kpair;
  }

  proc enc(pk : pkey, m : plaintext) : ciphertext = {
     var r, c;
     r <$ randd;
     c <- enc r pk m;
     return c;
  }

  proc dec(sk : skey, c : ciphertext) : plaintext option = {
     return dec sk c;
  }

}.

clone import PKE_ROM.PKE_ROM as PKEROM with
   type pkey <- pkey,
   type skey = pkey * skey,
   type plaintext <- plaintext,
   op   dplaintext <- dplaintext,
   lemma dplaintext_ll <- PKE.dplaintext_ll,
   type ciphertext <- ciphertext,
   type RO.in_t <- plaintext,
   type RO.out_t <- randomness,
   op   RO.dout <- fun _ => randd,
   type RO.d_in_t <- unit,
   type RO.d_out_t <- bool
   proof *.

const qH : { int | 0 <= qH } as ge0_qH.

const qV : { int | 0 <= qV } as ge0_qV.

const qP : { int | 0 <= qP } as ge0_qP.

const qHC : { int | 0 <= qHC } as ge0_qHC.

module (TT : PKEROM.Scheme) (H : POracle) = {
  proc kg() : pkey * skey = {
     var kpair;
     kpair <$ kg;
     return (kpair.`1, kpair);
  }

  proc enc(pk : pkey, m : plaintext) : ciphertext = {
     var r, c;
     r <@ H.get(m);
     c <- enc r pk m;
     return c;
  }

  proc dec(sk : skey, c : ciphertext) : plaintext option = {
     var m', r, c', rv;
     rv <- None;
     m' <- dec (sk.`2) c;
     if (m' <> None) {
        r  <@ H.get(oget m');
        c' <- enc r (sk.`1) (oget m');
        rv <- if c = c' then m' else None;
     }
     return rv;
  }

}.

module CO1(O : RO.RO) : POracle = {
  var pk : pkey
  var sk : PKE.skey
  var counter : int
  var i  : int
  var queried : plaintext list
  var bad : bool

  proc get(x : plaintext) : randomness = {
       var y <- witness;
       if (!x \in queried) {
          if (size queried = i) {
              O.sample(x);
              bad <- true;
          }
          else {
              y <@ O.get(x);
          }
          queried <- queried ++ [x];
       }
       else {
          if(!find (pred1 x) queried = i) {



              y <@ O.get(x);
          }
       }
       counter <- counter + 1;
       return y;
  }
}.

module Correctness_Adv1(O : RO.RO, A : PKEROM.CORR_ADV) = {

  module A = A(CO1(O))

  proc main'(pk : pkey, sk : PKE.skey, i : int) : plaintext = {
    var m;
    CO1.i <- i;
    O.init();
    CO1.counter <- 0;
    CO1.pk <- pk;
    CO1.sk <- sk;
    CO1.queried <- [];
    CO1.bad <- false;
    m <@ A.find(CO1.pk, (CO1.pk,CO1.sk));
    return m;
  }

  proc main() : unit = {
    var m;
    (CO1.pk, CO1.sk) <@ BasePKE.kg();
    m <@ main'(CO1.pk,CO1.sk,-1);
    CO1(O).get(m);
  }

}.

module B(A : PKEROM.CORR_ADV, O : RO.RO) : PKE.CORR_ADV = {
  proc find(pk : pkey, sk : PKE.skey) : plaintext = {
    var m;
    CO1.i <$ [0..qHC];
    m <@ Correctness_Adv1(O,A).main'(pk,sk,CO1.i);
    CO1(O).get(m);
    return if (0 <= CO1.i < size CO1.queried)
           then (nth witness CO1.queried CO1.i)
           else head witness (filter (fun x => !x \in CO1.queried) FinT.enum);
  }

  proc main() : bool = {
    var m,r,c,m';
    (CO1.pk, CO1.sk) <@ BasePKE.kg();
    m <@ find(CO1.pk, CO1.sk);
    r <@ O.get(m);
    c <- enc r CO1.pk m;
    m' <@ BasePKE.dec(CO1.sk, c);

    return m' <> Some m;
  }

}.

module CountO (O : VA_ORC) = {
  var c_cvo : int
  var c_pco : int
  var c_h   : int
  proc init () = { c_h <- 0; c_cvo <- 0; c_pco <- 0; }

  proc cvo(c : ciphertext) : bool = {
    var r;
    r <@ O.cvo(c);
    c_cvo <- c_cvo + 1;
    return r;
  }

  proc pco(m : plaintext, c : ciphertext) : bool = {
    var r;
    r <@ O.pco(m, c);
    c_pco <- c_pco + 1;
    return r;
  }
}.

module CountH(H:POracle) = {
  proc get(x:plaintext) = {
    var r;
    r <@ H.get(x);
    CountO.c_h <- CountO.c_h + 1;
    return r;
  }
}.

module Gm = {
  var m : plaintext
  var r : randomness
  var log : (plaintext, randomness) fmap
  var bad_corr : plaintext option
}.

module O_AdvOW = {
  var pk : pkey
  proc pco(m : plaintext, c : ciphertext) : bool = {
    var r, c';
    r  <@ RO.RO.get(m);
    c' <- enc r pk m;
    return c = c';
  }

  proc cvo(c:ciphertext) : bool = {
    var rv;
    rv <- false;
    if (c <> OW_PCVA.cc)
      rv <- find (fun m r => c = enc r pk m) RO.RO.m <> None;
    return rv;
  }
}.

module AdvOW (A:PCVA_ADV) = {
  import var OW_PCVA O_AdvOW

  module A = A(CountH(RO.RO), CountO(O_AdvOW))

  proc find(pk0:pkey, c:ciphertext) : plaintext option = {
    var m' : plaintext option;
    pk <- pk0;
    RO.RO.init();
    cc       <- c;
    CountO(O_AdvOW).init();
    m'       <@ A.find(pk,cc);
    return m';
  }
}.

module AdvOW_query (A:PCVA_ADV) = {
  import var OW_PCVA O_AdvOW

  module A = A(CountH(RO.RO), CountO(O_AdvOW))

  proc main(pk0:pkey, c:ciphertext) : unit = {
    var m' : plaintext option;
    pk <- pk0;
    RO.RO.init();
    cc       <- c;
    CountO(O_AdvOW).init();
    m'       <@ A.find(pk,cc);
  }

  proc find(pk0:pkey, c:ciphertext) : plaintext option = {
    var i : int;
    main(pk0, c);
    i        <$ [0 .. qH + qP - 1];
    return Some (nth witness (elems (fdom RO.RO.m)) i);
  }
}.

module AdvOWL_query (A:PCVA_ADV) = {
  proc find(pk0:pkey, c:ciphertext) : plaintext list = {
       AdvOW_query(A).find(pk0,c);
       return elems (fdom RO.RO.m);
  }
}.

module type PCOT = {
  proc pco(m : plaintext, c:ciphertext) : bool
}.

module type GT (PCO:PCOT) (RO:RO.RO) = {
  proc distinguish () : bool
}.

import RO.FullEager.

module H(RO:POracle) = {
  import var Gm
  proc get (x:plaintext) = {
    var r;
    if (x \notin log) {
      r <@ RO.get(x);
      log.[x] <- r;
    }
    return oget log.[x];
  }
}.

op incl ['a, 'b] (m1 m2: ('a, 'b) fmap) =
  forall x, x \in m1 => m1.[x] = m2.[x].

pred gamma_spread_ok(gamma_spread : real) =
 forall pk sk m c, (pk, sk) \in kg =>
   mu randd (fun r => enc r pk m = c) <= gamma_spread.

module G2_O (RO:POracle) = {
  import var OW_PCVA Gm

  proc pco(m : plaintext, c : ciphertext) : bool = {
    var m', r, c';
    m' <- dec (sk.`2) c;
    r  <@ H(RO).get(m);
    c' <- enc r sk.`1 m;
    bad_corr <- if (c = c' /\ m' <> Some m) then Some m else bad_corr;
    return c = c';
  }

  proc cvo(c:ciphertext) : bool = {
    var rv, m'  ;

    rv <- false;
    if (c <> cc) {
      m' <- dec (sk.`2) c;
      rv <- find (fun m r => c = enc r sk.`1 m) log <> None;
      if (m' <> None) {
        if (oget m' \in log) {
           bad_corr <-
            let f = find (fun m r => c = enc r sk.`1 m) log in
            if f <> None /\ (oget f).`1 <> oget m' then Some (oget f).`1 else bad_corr;
        } else {
          if (oget m' = Gm.m) {
            bad_corr <-
              let f = find (fun m r => c = enc r sk.`1 m) log in
               if f <> None /\ (oget f).`1 <> oget m' then Some (oget f).`1 else bad_corr;
          } else {
            bad_corr <-
              let f = find (fun m r => c = enc r sk.`1 m) log in
              if f <> None then Some (oget f).`1 else bad_corr;
          }
        }
      } else {
        bad_corr <-
          let f = find (fun m r => c = enc r sk.`1 m) log in
          if f <> None then Some (oget f).`1 else bad_corr;
      }
    }
    return rv;
  }
}.

module AdvCorr (A:PCVA_ADV) (RO:POracle) = {
  import var OW_PCVA Gm

  module H = H(RO)
  module O = G2_O(RO)
  module A = A(CountH(H), CountO(O))

  proc find(pk:pkey, sk:skey) : plaintext = {
    var m' : plaintext option;
    OW_PCVA.sk <- sk;
    Gm.log <- empty; bad_corr <- None;
    m        <$ dplaintext;
    r        <@ RO.get(m);
    cc       <- enc r pk m;

    CountO(O).init();
    m'       <@ A.find(pk,cc);
    bad_corr <- if dec sk.`2 cc = m' /\ Some m <> m' then Some m else bad_corr;
    return oget Gm.bad_corr;
  }
}.

op inv_G2_corr (log ro : (plaintext, randomness) fmap) (sk:skey)
        bad_corr gm gr =
  incl log ro /\ gm \in ro /\ gr = oget ro.[gm] /\
  (bad_corr <> None =>
      let m = oget bad_corr in
      let r = oget ro.[m] in
      let c = enc r sk.`1 m in
      let m' = dec sk.`2 c in
      m \in ro /\ m' <> Some m).
