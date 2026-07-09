(*
 * A formal verification of the Pedersen commitment scheme
 *
 * Pedersen, Torben Pryds
 * "Non-interactive and information-theoretic secure verifiable secret sharing"
 *)
require import Real.
require (****) DLog.

clone DLog as DL.
import DL.G DL.GP DL.FD DL.GP.ZModE.

require (*--*) Commitment.

(* Pedersen protocol types *)
theory PedersenTypes.
  type value        = group.
  type message      = exp.
  type commitment   = group.
  type openingkey   = exp.
end PedersenTypes.
export PedersenTypes.

(* Instantiate the Commitment scheme with the above types *)
clone import Commitment as CM with
  type CommitmentProtocol.value      <- value,
  type CommitmentProtocol.message    <- message,
  type CommitmentProtocol.commitment <- commitment,
  type CommitmentProtocol.openingkey <- openingkey.
export CommitmentProtocol.

module Pedersen : CommitmentScheme = {
  proc gen() : value = {
    var x, h;
    x <$ dt;
    h <- g ^ x;
    return h;
  }

  proc commit(h: value, m: message) : commitment * openingkey = {
    var c, d;
    d <$ dt;
    c <- (g ^ d) * (h ^ m);
    return (c, d);
  }

  proc verify(h: value, m: message, c: commitment, d: openingkey) : bool = {
    var c';
    c' <- (g ^ d) * (h ^ m);
    return (c = c');
  }
}.

module DLogAttacker(B:Binder) : DL.DLog.Adversary = {
  proc guess (h: group) : exp option = {

    var x, c, m, m', d, d';
    (c, m, d, m', d') <@ B.bind(h);
    if ((c = g ^ d * h ^ m) /\ (c = g ^ d' * h ^ m') /\ (m <> m'))
      x <- Some((d - d') * inv (m' - m));
    else
      x <- None;

    return x;
  }
}.

section PedersenSecurity.

  (* Correctness *)
  lemma pedersen_correctness:
    hoare[Correctness(Pedersen).main: true ==> res].
  proof. proc; inline *;auto. qed.

  local module FakeCommit(U:Unhider) = {
    proc main() : bool = {
      var b, b', x, h, c, d;
      var m0, m1 : exp;

      (* Clearly, there are many useless lines, but their presence helps for the proofs *)
      x <$ dt;
      h <- g^x;
      (m0, m1) <@ U.choose(h);
      b <$ {0,1};
      d <$ dt;
      c <- g^d; (* message independent - fake commitment *)
      b' <@ U.guess(c);

      return (b = b');
    }
  }.

  local lemma hi_ll (U<:Unhider):
    islossless U.choose =>
    islossless U.guess =>
    islossless FakeCommit(U).main.
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  move=> Uc_ll Ug_ll; proc. call Ug_ll; wp; rnd predT; rnd predT; call Uc_ll; wp; rnd predT; skip. smt(dt_ll DBool.dbool_ll).
qed.

  (* Perfect hiding *)
  local lemma fakecommit_half (U<:Unhider) &m:
    islossless U.choose =>
    islossless U.guess =>
    Pr[FakeCommit(U).main() @ &m : res] = 1%r/2%r.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    move=> Uc_ll Ug_ll.
    byphoare (_ : true ==> _) => //.
    proc; swap 4 3.
    rnd (pred1 b'); call Ug_ll; wp; rnd predT; call Uc_ll; wp; rnd predT; skip => />.
    smt(dt_ll DBool.dbool_ll DBool.dbool1E).
  qed.

  local lemma phi_hi (U<:Unhider) &m:
    Pr[HidingExperiment(Pedersen,U).main() @ &m : res] =
    Pr[FakeCommit(U).main() @ &m : res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    byequiv => //; proc; inline *.
    wp; call (: true); wp.
    rnd (fun d => d + x0{1} * (if b{1} then m1{1} else m0{1}))
        (fun d => d - x0{1} * (if b{1} then m1{1} else m0{1})).
    wp; rnd; call (: true); wp; rnd; skip => />.
    move=> x0 _ r b _; do!split; smt(expD expM ZModpField.addrK ZModpField.subrK).
  qed.

  (* Perfect hiding - QED *)
  lemma pedersen_perfect_hiding (U<:Unhider) &m:
    islossless U.choose =>
    islossless U.guess =>
    Pr[HidingExperiment(Pedersen,U).main() @ &m : res] = 1%r/2%r.
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    move=> Uc_ll Ug_ll.
    by rewrite (phi_hi U &m) (fakecommit_half U &m).
  qed.

  (* Computational binding - QED *)
  lemma pedersen_computational_binding (B<:Binder) &m:
    Pr[BindingExperiment(Pedersen, B).main() @ &m : res] =
    Pr[DL.DLog.DLogExperiment(DLogAttacker(B)).main() @ &m : res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    byequiv => //; proc; inline *.
    wp; call (: true); wp; rnd; skip => /> x _ [c m d m' d'] /= hc1 hc2 hm.
    have heq : d + x * m = d' + x * m'.
      have : g ^ (d + x * m) = g ^ (d' + x * m').
      + by rewrite expD expM (expD g d') (expM g x) -hc1 -hc2.
      by rewrite pow_bij.
    have hneq : m' - m <> ZModpRing.zeror by smt(ZModpRing.subr_eq0).
    have hdiff : d - d' = x * (m' - m) by ring heq.
    have -> : (d - d') / (m' - m) = x.
      have hd: (d - d') = x * (m' - m) by ring heq.
      by rewrite hd ZModpField.mulrK.
    done.
  qed.

  (*
     The following two are to compare probability directly with book discrete
     logarithm experiment. Not strictly necessary though, only for completeness.
  *)
  local lemma std_red_dl_bridge (B<:Binder) &m:
    Pr[DL.DLog.DLogExperiment(DLogAttacker(B)).main() @ &m : res] <=
    Pr[DL.DLog.DLogStdExperiment(DL.StdRedAdversary(DLogAttacker(B))).main() @ &m : res].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    apply (DL.dlog_standard_reduction (DLogAttacker(B)) &m).
  qed.

  lemma pedersen_std_computational_binding (B<:Binder) &m:
    Pr[BindingExperiment(Pedersen, B).main() @ &m : res] <=
    Pr[DL.DLog.DLogStdExperiment(DL.StdRedAdversary(DLogAttacker(B))).main() @ &m : res]
  by rewrite(pedersen_computational_binding B &m); apply (std_red_dl_bridge B &m).

end section PedersenSecurity.

print pedersen_correctness.
print pedersen_perfect_hiding.
print pedersen_computational_binding.