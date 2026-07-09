(*
 * A formal verification of the Schnorr proof of knowledge
 *)
require import Int.
require import Real.
require import Distr.
require (****) Group.

clone Group.CyclicGroup as G.

axiom prime_p : IntDiv.prime G.order.

clone G.PowZMod as GP with
  lemma prime_order <- prime_p.

clone GP.FDistr as FD.

clone GP.ZModE.ZModpField as ZPF.

import G GP GP.ZModE FD.

require (*--*) SigmaProtocol.

(* Schnorr protocol types *)
theory SchnorrTypes.
  type statement = group.
  type witness   = exp.
  type message   = group.
  type secret    = exp.
  type challenge = exp.
  type response  = exp.

  op R_DL (h : group) (w : exp) = (h = g ^ w).
end SchnorrTypes.
export SchnorrTypes.

(* Instantiate the Sigma scheme with the above types *)
clone import SigmaProtocol as SP with
  type SigmaProtocol.statement <- statement,
  type SigmaProtocol.witness   <- witness,
  type SigmaProtocol.message   <- message,
  type SigmaProtocol.secret    <- secret,
  type SigmaProtocol.challenge <- challenge,
  type SigmaProtocol.response  <- response,
  op   SigmaProtocol.R         = R_DL,
  op   SigmaProtocol.de        = dt.
export SigmaProtocol.

module SchnorrPK : SigmaScheme = {
  proc gen() : statement * witness = {
    var h, w;
    w <$ dt;
    if (w = GP.ZModE.zero) {
    (* A loop would be better, however the support for while loops is poor *)
      w <- GP.ZModE.zero;
    }
    h <- g ^ w;
    return (h, w);
  }

  proc commit(h: statement, w: witness) : message * secret = {
    var r, a;
    r <$ dt;
    a <- g ^ r;
    return (a, r);
  }

  proc test(h: statement, a: message) : challenge = {
    var e;
    e <$ dt;
    return e;
  }

  proc respond(sw: statement * witness, ms: message * secret, e: challenge) : response = {
    var z, w, r;
    w <- snd sw;
    r <- snd ms;
    z <- r + e * w;
    return z;
  }

  proc verify(h: statement, a: message, e: challenge, z: response) : bool = {
    var v, v';
    v <- a * (h ^ e);
    v' <- g ^ z;
    return (v = v');
  }
}.

module SchnorrPKAlgorithms : SigmaAlgorithms = {
  proc soundness(h: statement, a: message, e: challenge, z: response, e': challenge, z': response) : witness option = {
    var sto, w, v, v';

    v  <- (g ^ z  = a * (h ^ e));
    v' <- (g ^ z' = a * (h ^ e'));
    if (e <> e' /\ v /\ v') {
      w <- (z - z') / (e - e');
      sto <- Some(w);
    } else {
      sto <- None;
    }

    return sto;
  }

  proc simulate(h: statement, e: challenge) : message * challenge * response = {
    var a, z;

    z  <$ dt;
    a  <- (g ^ z) * (h ^ (-e));

    return (a, e, z);
  }
}.

section SchnorrPKSecurity.
  (* Completeness *)
  lemma schnorr_proof_of_knowledge_completeness_ll:
    islossless Completeness(SchnorrPK).main.
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  proc; islossless.
qed.

  lemma schnorr_proof_of_knowledge_completeness h w' &m:
    R h w' =>
    Pr[Completeness(SchnorrPK).main(h, w') @ &m : res] = 1%r.
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  move=> Rhw.
  byphoare (_: arg = (h, w') ==> _) => //.
  proc; inline *.
  wp.
  rnd predT.
  wp.
  rnd predT.
  wp; skip.
  move=> &hr /=.
  smt(dt_ll dt_fu expD expM).
qed.

  (* Special soundness *)
  lemma schnorr_proof_of_knowledge_special_soundness (h: statement) msg (ch ch' r r' : exp) &m:
    ch <> ch' =>
    g ^ r  = msg*(h ^ ch ) =>
    g ^ r' = msg*(h ^ ch') =>
    Pr[SpecialSoundnessExperiment(SchnorrPK, SchnorrPKAlgorithms).main(h, msg, ch, r, ch', r') @ &m : (res <> None /\ R h (oget res))] = 1%r.
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  move=> Hneq Hr Hr'.
  byphoare (_: arg = (h, msg, ch, r, ch', r') ==> _) => //.
  proc; inline *.
  auto => />.
  move=> _ _ _.
  split; [| split; [by rewrite eq_sym Hr | by rewrite eq_sym Hr']].
  rewrite /R /R_DL.
  rewrite log_bij loggK.
  have Hr_l: r = loge msg + ch * loge h by rewrite log_bij !(loggK, logDr, logrzM) in Hr.
  have Hr'_l: r' = loge msg + ch' * loge h by rewrite log_bij !(loggK, logDr, logrzM) in Hr'.
  rewrite Hr_l Hr'_l.
  field.
  have ->: (-ch') + ch = ch - ch' by ring.
  rewrite GP.ZModE.ZModpRing.subr_eq0; exact Hneq.
qed.

  (* Special honest verifier zero knowledge *)
  lemma schnorr_proof_of_knowledge_shvzk (D<: SigmaTraceDistinguisher) &m:
    Pr[SimulateHonestVerifier(SchnorrPK, SchnorrPKAlgorithms, D).gameIdeal() @ &m : res] =
    Pr[SimulateHonestVerifier(SchnorrPK, SchnorrPKAlgorithms, D).gameReal() @ &m : res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    byequiv => //; proc; inline *.
    (* Show the verification in the simulator always passes *)
    rcondt{1} 25.
      move=> &m0; auto => /> *.
      smt(mulcA expN mulVc mulc1).
    (* Show the while loop never executes *)
    rcondf{1} 28.
      move=> &m0; auto.
    (* Match D calls and push through deterministic ops *)
    wp; call (: true); wp.
    (* Swap e1 on right before r so samples align: z1↔r, e↔e1 *)
    swap{2} 12 -5.
    wp.
    (* Couple z1 (left) with r (right) via bijection *)
    rnd (fun z => z - e{1} * w0{1}) (fun r0 => r0 + e1{2} * w0{2}).
    wp.
    (* Couple e (left) with e1 (right) - identity *)
    rnd.
    wp.
    (* Handle unused r on left *)
    rnd{1}.
    wp.
    (* Couple w0 *)
    rnd.
    wp; skip.
    move=> /> *.
    do!split => //; smt(dt_ll dt_fu dt_funi expD expM expN expB mulcC mulcV mulc1 mul1c
                        GP.ZModE.ZModpRing.addrK GP.ZModE.ZModpRing.addrN
                        GP.ZModE.ZModpRing.addrC GP.ZModE.ZModpRing.addrA
                        GP.ZModE.ZModpRing.subrr GP.ZModE.ZModpRing.add0r
                        GP.ZModE.ZModpRing.addr0 GP.ZModE.ZModpRing.subrK).
  qed.
  (* The above three theorems prove that the Schnorr proof of knowledge is a Sigma protocol *)

end section SchnorrPKSecurity.

print schnorr_proof_of_knowledge_completeness.
print schnorr_proof_of_knowledge_special_soundness.
print schnorr_proof_of_knowledge_shvzk.