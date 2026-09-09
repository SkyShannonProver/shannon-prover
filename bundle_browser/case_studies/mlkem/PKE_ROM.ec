require import AllCore List Distr DBool PROM FinType SmtMap FSet.

require   LorR.

abstract theory PKE.

type pkey.

type skey.

type plaintext.

type ciphertext.

module type Scheme = {
  proc kg() : pkey * skey
  proc enc(pk:pkey, m:plaintext)  : ciphertext
  proc dec(sk:skey, c:ciphertext) : plaintext option
}.

module type CORR_ADV = {
  proc find(pk : pkey, sk : skey) : plaintext
}.

module Correctness_Adv (S:Scheme, A : CORR_ADV) = {
  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var c  : ciphertext;
    var m  : plaintext;
    var m' : plaintext option;

    (pk, sk) <@ S.kg();
    m        <@ A.find(pk,sk);
    c        <@ S.enc(pk, m);
    m'       <@ S.dec(sk, c);
    return (m' <> Some m);
  }
}.

module type Adversary = {
  proc choose(pk:pkey)     : plaintext * plaintext
  proc guess(c:ciphertext) : bool
}.

module CPA (S:Scheme, A:Adversary) = {
  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var m0, m1 : plaintext;
    var c : ciphertext;
    var b, b' : bool;

    (pk, sk) <@ S.kg();
    (m0, m1) <@ A.choose(pk);
    b        <$ {0,1};
    c        <@ S.enc(pk, b ? m1 : m0);
    b'       <@ A.guess(c);
    return (b' = b);
  }
}.

module CPA_L (S:Scheme, A:Adversary) = {
  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var m0, m1 : plaintext;
    var c : ciphertext;
    var b' : bool;

    (pk, sk) <@ S.kg();
    (m0, m1) <@ A.choose(pk);
    c        <@ S.enc(pk, m0);
    b'       <@ A.guess(c);
    return b';
  }
}.

module CPA_R (S:Scheme, A:Adversary) = {
  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var m0, m1 : plaintext;
    var c : ciphertext;
    var b' : bool;

    (pk, sk) <@ S.kg();
    (m0, m1) <@ A.choose(pk);
    c        <@ S.enc(pk, m1);
    b'       <@ A.guess(c);
    return b';
  }
}.

clone import LorR with
    type input <- unit.

module type OW_CPA_ADV = {
  proc find(pk : pkey, c:ciphertext) : plaintext option
}.

clone FinType as MFinT with
  type t <- plaintext.

op [lossless full uniform] dplaintext : plaintext distr.

op eps_msg = 1%r / MFinT.card%r.

module OW_CPA (S:Scheme, A: OW_CPA_ADV) = {
  var pk : pkey
  var sk : skey
  var m  : plaintext
  var cc : ciphertext
  var m' : plaintext option

  proc main_perfect() = {
    (pk, sk) <@ S.kg();
    m        <$ dplaintext;
    cc       <@ S.enc(pk, m);
    m'       <@ A.find(pk,cc);
    return (m' = Some m);

  }

  module O = {
    proc pco(sk, m : plaintext, c : ciphertext) : bool = {
      var m'';
      m''   <@ S.dec(sk, c);
      return m'' = Some m;
    }
  }

  proc main() : bool = {
    var b  : bool;

    (pk, sk) <@ S.kg();
    m        <$ dplaintext;
    cc       <@ S.enc(pk, m);
    m'       <@ A.find(pk,cc);
    b        <@ O.pco(sk, oget m',cc);
    return if m' = None then false else b;
  }
}.

module BOWp(S : Scheme, A :  OW_CPA_ADV) : CORR_ADV = {
   var m'' : plaintext option

   proc find(pk : pkey, sk : skey) : plaintext = {
       OW_CPA.m  <$ dplaintext;
       return OW_CPA.m;
   }

   proc main() : bool = {
    var pk,sk;
    (pk, sk) <@ S.kg();
    find(pk,sk);
    OW_CPA.cc <@ S.enc(pk, OW_CPA.m);
    OW_CPA.m' <@ A.find(pk,OW_CPA.cc);
    m''       <@ S.dec(sk, OW_CPA.cc);
    return (m'' <> Some OW_CPA.m);
   }
}.

module type OWL_CPA_ADV = {
  proc find(pk : pkey, c:ciphertext) : plaintext list
}.

module OWL_CPA (S:Scheme, A: OWL_CPA_ADV) = {
  var pk : pkey
  var sk : skey
  var m  : plaintext
  var cc : ciphertext
  var l : plaintext list

  proc main() = {
    (pk, sk) <@ S.kg();
    m        <$ dplaintext;
    cc       <@ S.enc(pk, m);
    l       <@ A.find(pk,cc);
    return (m \in l);

  }
}.

theory OWvsIND.

module Bowl(A :  OWL_CPA_ADV) : Adversary = {
   var m0, m1  : plaintext
   var pk      : pkey
   var l       : plaintext list

   proc choose(_pk : pkey) : plaintext * plaintext = {
     pk <- _pk;
     m0 <$ dplaintext;
     m1 <$ dplaintext;
     return (m0,m1);
   }

   proc guess(c : ciphertext) : bool = {
      var b;
      b <$ {0,1};
      l <@ A.find(pk,c);
      return if (m0 \in l = m1 \in l)
             then b
             else if (m0 \in l)
                  then false
                  else true;
   }
}.

pred bad(gB : glob Bowl) = (gB.`2 \in gB.`1 = gB.`3 \in gB.`1).

module BL(A : OW_CPA_ADV) : OWL_CPA_ADV = {
  proc find(pk : pkey, c : ciphertext) : plaintext list = {
     var m';
     m' <@ A.find(pk,c);
     return if m' = None then [] else [oget m'];
  }
}.

end OWvsIND.

end PKE.

abstract theory PKE_ROM.

type pkey.

type skey.

type plaintext.

type ciphertext.

clone import FullRO as RO.

module type Oracle = {
  include FRO [init, get]
}.

module type POracle = {
  include FRO [get]
}.

module type Scheme(H : POracle) = {
  proc kg() : pkey * skey
  proc enc(pk:pkey, m:plaintext)  : ciphertext
  proc dec(sk:skey, c:ciphertext) : plaintext option
}.

module type Adversary (H : POracle) = {
  proc choose(pk:pkey)     : plaintext * plaintext
  proc guess(c:ciphertext) : bool
}.

module CPA (H : Oracle, S:Scheme, A:Adversary) = {
  module A = A(H)

  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var m0, m1 : plaintext;
    var c : ciphertext;
    var b, b' : bool;

    H.init();
    (pk, sk) <@ S(H).kg();
    (m0, m1) <@ A.choose(pk);
    b        <$ {0,1};
    c        <@ S(H).enc(pk, b ? m1 : m0);
    b'       <@ A.guess(c);
    return (b' = b);
  }
}.

module CPA_L (H : Oracle, S:Scheme, A:Adversary) = {
  module A = A(H)

  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var m0, m1 : plaintext;
    var c : ciphertext;
    var b' : bool;

    H.init();
    (pk, sk) <@ S(H).kg();
    (m0, m1) <@ A.choose(pk);
    c        <@ S(H).enc(pk, m0);
    b'       <@ A.guess(c);
    return b';
  }
}.

module CPA_R (H : Oracle, S:Scheme, A:Adversary) = {
  module A = A(H)

  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var m0, m1 : plaintext;
    var c : ciphertext;
    var b' : bool;

    H.init();
    (pk, sk) <@ S(H).kg();
    (m0, m1) <@ A.choose(pk);
    c        <@ S(H).enc(pk, m1);
    b'       <@ A.guess(c);
    return b';
  }
}.

clone import LorR with
    type input <- unit.

module type CCA_ORC = {
  proc dec(c:ciphertext) : plaintext option
}.

module type CCA_ADV (H : POracle, O:CCA_ORC) = {
  proc choose(pk:pkey)     : plaintext * plaintext
  proc guess(c:ciphertext) : bool {O.dec}
}.

module CCA (H : Oracle, S:Scheme, A:CCA_ADV) = {
  var cstar : ciphertext option
  var sk : skey

  module O = {
    proc dec(c:ciphertext) : plaintext option = {
      var m : plaintext option;

      m <- None;
      if (Some c <> cstar) {
        m   <@ S(H).dec(sk, c);
      }
      return m;
    }
  }

  module A = A(H, O)

  proc main() : bool = {
    var pk : pkey;
    var m0, m1 : plaintext;
    var c : ciphertext;
    var b, b' : bool;

    H.init();
    cstar    <- None;
    (pk, sk) <@ S(H).kg();
    (m0, m1) <@ A.choose(pk);
    b        <$ {0,1};
    c        <@ S(H).enc(pk, b ? m1 : m0);
    cstar    <- Some c;
    b'       <@ A.guess(c);
    return (b' = b);
  }
}.

module type CORR_ADV (H : POracle) = {
  proc find(pk : pkey, sk : skey) : plaintext
}.

module Correctness_Adv (H : Oracle, S:Scheme, A : CORR_ADV) = {
  module A = A(H)

  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var c  : ciphertext;
    var m  : plaintext;
    var m' : plaintext option;

    H.init();
    (pk, sk) <@ S(H).kg();
    m        <@ A.find(pk,sk);
    c        <@ S(H).enc(pk, m);
    m'       <@ S(H).dec(sk, c);
    return (m' <> Some m);
  }
}.

module type VA_ORC = {
  proc cvo(c:ciphertext) : bool
  proc pco(m : plaintext, c:ciphertext) : bool
}.

module type PCVA_ADV (H : POracle, O: VA_ORC) = {
  proc find(pk : pkey, c:ciphertext) : plaintext option
}.

op [lossless] dplaintext : plaintext distr.

module OW_PCVA (H : Oracle, S:Scheme, A: PCVA_ADV) = {
  var sk : skey
  var cc : ciphertext

  module O = {
    proc cvo(c:ciphertext) : bool = {
      var m : plaintext option;

      m <- None;
      if (c <> cc) { m   <@ S(H).dec(sk, c); }
      return (m <> None);
    }

    proc pco(m : plaintext, c : ciphertext) : bool = {
      var m';
      m'   <@ S(H).dec(sk, c);
      return m' = Some m;
    }
  }

  module A = A(H,O)

  proc main() : bool = {
    var pk : pkey;
    var m  : plaintext;
    var m' : plaintext option;
    var b;

    H.init();
    (pk, sk) <@ S(H).kg();
    m        <$ dplaintext;
    cc       <@ S(H).enc(pk, m);
    m'       <@ A.find(pk,cc);
    b        <@ O.pco(oget m',cc);
    return if m' = None then false else b;
  }
}.

end PKE_ROM.
