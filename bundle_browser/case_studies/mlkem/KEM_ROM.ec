require import AllCore List Distr DBool PROM.

require   LorR.

abstract theory KEM.

type pkey.

type skey.

type key.

type ciphertext.

op [lossless uniform full]dkey : key distr.

module type Scheme = {
  proc kg() : pkey * skey
  proc enc(pk:pkey)  : ciphertext * key
  proc dec(sk:skey, c:ciphertext) : key option
}.

module Correctness(S:Scheme) = {
  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var c  : ciphertext;
    var k  : key;
    var k' : key option;

    (pk, sk) <@ S.kg();
    (c,k)    <@ S.enc(pk);
    k'       <@ S.dec(sk,c);
    return (k' <> Some k);

  }
}.

module type Adversary = {
  proc guess(pk : pkey, c:ciphertext, k : key) : bool
}.

module CPA (S:Scheme, A:Adversary) = {
  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var k1 : key;
    var ck0 : ciphertext * key;
    var b, b' : bool;

    (pk, sk) <@ S.kg();
    b        <$ {0,1};
    k1        <$ dkey;
    ck0      <@ S.enc(pk);
    b'       <@ A.guess(pk, ck0.`1, if b then k1 else ck0.`2);
    return (b' = b);
  }
}.

module CPA_L (S:Scheme, A:Adversary) = {
  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var k1 : key;
    var ck0 : ciphertext * key;
    var b' : bool;

    (pk, sk) <@ S.kg();
    k1        <$ dkey;
    ck0      <@ S.enc(pk);
    b'       <@ A.guess(pk, ck0.`1, ck0.`2);
    return b';
  }
}.

module CPA_R (S:Scheme, A:Adversary) = {
  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var k1 : key;
    var ck0 : ciphertext * key;
    var b' : bool;

    (pk, sk) <@ S.kg();
    k1        <$ dkey;
    ck0      <@ S.enc(pk);
    b'       <@ A.guess(pk, ck0.`1, k1);
    return b';
  }
}.

clone import LorR as LR with
     type input <- unit.

module type CCA_ORC = {
  proc dec(c:ciphertext) : key option
}.

module type CCA_ADV (O:CCA_ORC) = {
  proc guess(pk : pkey, c:ciphertext, k : key) : bool
}.

module CCA (S:Scheme, A:CCA_ADV) = {
  var cstar : ciphertext option
  var sk : skey

  module O = {
    proc dec(c:ciphertext) : key option = {
      var k : key option;

      k <- None;
      if (Some c <> cstar) {
        k  <@ S.dec(sk, c);
      }
      return k;
    }
  }

  module A = A(O)

  proc main() : bool = {
    var pk : pkey;
    var k1 :key;
    var ck0 : ciphertext * key;
    var b, b' : bool;

    cstar    <- None;
    (pk, sk) <@ S.kg();
    k1 <$ dkey;
    b        <$ {0,1};
    ck0        <@ S.enc(pk);
    cstar    <- Some ck0.`1;
    b'       <@ A.guess(pk, ck0.`1, if b then k1 else ck0.`2);
    return (b' = b);
  }
}.

end KEM.

abstract theory KEM_ROM.

type pkey.

type skey.

type key.

type ciphertext.

op [lossless uniform full]dkey : key distr.

clone import FullRO as RO.

module type Oracle = {
  include FRO [init, get]
}.

module type POracle = {
  include FRO [get]
}.

module type Scheme(O : POracle) = {
  proc kg() : pkey * skey
  proc enc(pk:pkey)  : ciphertext * key
  proc dec(sk:skey, c:ciphertext) : key option
}.

module Correctness(H : Oracle, S:Scheme) = {
  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var c  : ciphertext;
    var k  : key;
    var k' : key option;

    H.init();
    (pk, sk) <@ S(H).kg();
    (c,k)    <@ S(H).enc(pk);
    k'       <@ S(H).dec(sk,c);
    return (k' <> Some k);

  }
}.

module type CCA_ORC = {
  proc dec(c:ciphertext) : key option
}.

module type CCA_ADV (H : POracle, O:CCA_ORC) = {
  proc guess(pk : pkey, c:ciphertext, k : key) : bool
}.

module CCA(H : Oracle, S:Scheme, A:CCA_ADV) = {
  var cstar : ciphertext option
  var sk : skey

  module O = {
    proc dec(c:ciphertext) : key option = {
      var k : key option;

      k <- None;
      if (Some c <> cstar) {
        k  <@ S(H).dec(sk, c);
      }
      return k;
    }
  }

  module A = A(H,O)

  proc main() : bool = {
    var pk : pkey;
    var k1 :key;
    var ck0 : ciphertext * key;
    var b, b' : bool;

    H.init();
    cstar    <- None;
    (pk, sk) <@ S(H).kg();
    k1 <$ dkey;
    b        <$ {0,1};
    ck0        <@ S(H).enc(pk);
    cstar    <- Some ck0.`1;
    b'       <@ A.guess(pk, ck0.`1, if b then k1 else ck0.`2);
    return (b' = b);
  }
}.

end KEM_ROM.

theory KEM_ROM_x2.

type pkey.

type skey.

type key.

type ciphertext.

op [lossless uniform full]dkey : key distr.

clone import FullRO as RO1.

clone import FullRO as RO2.

module type Oracle_x2 = {
  proc init() : unit
  proc get1(_: RO1.in_t) : RO1.out_t
  proc get2(_: RO2.in_t) : RO2.out_t
}.

module type POracle_x2 = {
  include Oracle_x2 [get1,get2]
}.

module RO_x2(H1 : RO1.RO, H2 : RO2.RO): Oracle_x2 = {
  proc init() : unit = {
     H1.init();
     H2.init();
  }
  proc get1 = H1.get
  proc get2 = H2.get
}.

module type Scheme(O : POracle_x2) = {
  proc kg() : pkey * skey
  proc enc(pk:pkey)  : ciphertext * key
  proc dec(sk:skey, c:ciphertext) : key option
}.

module Correctness(H : Oracle_x2, S:Scheme) = {
  proc main() : bool = {
    var pk : pkey;
    var sk : skey;
    var c  : ciphertext;
    var k  : key;
    var k' : key option;

    H.init();
    (pk, sk) <@ S(H).kg();
    (c,k)    <@ S(H).enc(pk);
    k'       <@ S(H).dec(sk,c);
    return (k' <> Some k);

  }
}.

module type CCA_ORC = {
  proc dec(c:ciphertext) : key option
}.

module type CCA_ADV (H : POracle_x2, O:CCA_ORC) = {
  proc guess(pk : pkey, c:ciphertext, k : key) : bool
}.

module CCA(H : Oracle_x2, S:Scheme, A:CCA_ADV) = {
  var cstar : ciphertext option
  var sk : skey

  module O = {
    proc dec(c:ciphertext) : key option = {
      var k : key option;

      k <- None;
      if (Some c <> cstar) {
        k  <@ S(H).dec(sk, c);
      }
      return k;
    }
  }

  module A = A(H,O)

  proc main() : bool = {
    var pk : pkey;
    var k1 :key;
    var ck0 : ciphertext * key;
    var b, b' : bool;

    H.init();
    cstar    <- None;
    (pk, sk) <@ S(H).kg();
    k1 <$ dkey;
    b        <$ {0,1};
    ck0        <@ S(H).enc(pk);
    cstar    <- Some ck0.`1;
    b'       <@ A.guess(pk, ck0.`1, if b then k1 else ck0.`2);
    return (b' = b);
  }
}.

end KEM_ROM_x2.
