require import AllCore Int Real List FinType DBool.

abstract theory IDS.

type PK, SK, W, C, Z, Pstate.

type transcript = W*C*Z.

module type Prover = {
  proc keygen(): PK*SK
  proc commit(sk:SK): W
  proc response(sk:SK, c:C): Z option
}.

module type Verifier ={
  proc challenge(w:W, pk:PK): C
  proc verify(pk:PK, w:W, c:C, z:Z): bool
}.

module type Adv_Imp = {
  proc commit(pk:PK): W
  proc response(pk:PK, c:C): Z
}.

module Imp_Game (P: Prover, V: Verifier, A: Adv_Imp) = {

  proc main() = {
    var sk, pk,w,c,z,result;

    (pk,sk) <@ P.keygen();
    w <@ A.commit(pk);
    c <@ V.challenge(w,pk);
    z <@ A.response(pk, c);
    result <@ V.verify(pk,w,c,z);
    return result;
  }
}.

module type HVZK_Sim = {
  proc get_trans(pk:PK) : transcript option
}.

module Honest_Execution (P: Prover, V: Verifier) = {

  proc get_trans(pk:PK, sk:SK) = {
    var w,c,z,r;

    w <@ P.commit(sk);
    c <@ V.challenge(w,pk);
    z <@ P.response(sk, c);
    r <- if z = None then None else Some (w,c,oget z);
    return r;
  }
}.

module type HVZK_Oracle = {
  proc get_trans() : transcript option
}.

module HVZK_Sim_Oracle (Sim :HVZK_Sim) : HVZK_Oracle = {
  var pk : PK
  proc init (pki : PK) : unit = {
    pk <- pki;
  }

  proc get_trans() = {
    var trans;
    trans <@ Sim.get_trans(pk);
    return trans;
  }
}.

module HVZK_HE_Oracle (P : Prover, V: Verifier ) : HVZK_Oracle = {
  var pk : PK
  var sk : SK
  proc init (pki : PK, ski : SK) : unit = {
    pk <- pki;
    sk <- ski;
  }

  proc get_trans() = {
    var trans;
    trans <@ Honest_Execution(P,V).get_trans(pk,sk);
    return trans;
  }
}.

module type HVZK_Distinguisher (O: HVZK_Oracle) = {
  proc distinguish (pk : PK): bool
}.

module HVZK_Game (Sim: HVZK_Sim, P: Prover, V: Verifier, D: HVZK_Distinguisher) = {
  module OSim = HVZK_Sim_Oracle(Sim)
  module OHE = HVZK_HE_Oracle(P,V)

  proc main(n: int, b:bool) = {
    var sk, pk, result;

    (pk, sk) <@ P.keygen();
    if(b) {
      OSim.init(pk);
      result <@ D(OSim).distinguish(pk);
    } else {
      OHE.init(pk, sk);
      result <@ D(OHE).distinguish(pk);
    }
    return result;
  }
}.

end IDS.
