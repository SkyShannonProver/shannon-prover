(* -------------------------------------------------------------------- *)
require import AllCore Int Real Distr DBool.
require (*--*) DiffieHellman PKE_CPA.

(* ---------------- Sane Default Behaviours --------------------------- *)
pragma +implicits.

(* ---------------------- Let's Get Started --------------------------- *)
(** Assumption: set DDH *)
(*** WARNING: DiffieHellman is really out of date ***)
clone DiffieHellman as DH.
import DH.DDH DH.G DH.GP DH.FD DH.GP.ZModE.

clone DH.GP.ZModE.ZModpField as ZPF.

(** Construction: a PKE **)
type pkey = group.
type skey = exp.
type ptxt = group.
type ctxt = group * group.

clone import PKE_CPA as PKE with
  type pkey <- pkey,
  type skey <- skey,
  type ptxt <- ptxt,
  type ctxt <- ctxt.

(** Concrete Construction: Hashed ElGammal **)

module ElGamal : Scheme = {
  proc kg(): pkey * skey = {
    var sk;

    sk <$ dt;
    return (g ^ sk, sk);
  }

  proc enc(pk:pkey, m:ptxt): ctxt = {
    var y;

    y <$ dt;
    return (g ^ y, pk ^ y * m);
  }

  proc dec(sk:skey, c:ctxt): ptxt option = {
    var gy, gm;

    (gy, gm) <- c;
    return Some (gm * gy ^ (-sk));
  }
}.

(** Reduction: from a PKE adversary, construct a DDH adversary *)
module DDHAdv (A:Adversary) = {
  proc guess (gx, gy, gz) : bool = {
    var m0, m1, b, b';

    (m0, m1) <@ A.choose(gx);
    b        <$ {0,1};
    b'       <@ A.guess(gy, gz * (b?m1:m0));
    return b' = b;
  }
}.

(** We now prove that, for all adversary A, we have:
      `| Pr[CPA(ElGamal,A).main() @ &m : res] - 1%r/2%r |
      = `| Pr[DDH0(DDHAdv(A)).main() @ &m : res]
           - Pr[DDH1(DDHAdv(A)).main() @ &m : res] |.        **)
section Security.
  declare module A <: Adversary.
  declare axiom Ac_ll: islossless A.choose.
  declare axiom Ag_ll: islossless A.guess.

  local lemma cpa_ddh0 &m:
      Pr[CPA(ElGamal,A).main() @ &m : res] =
      Pr[DDH0(DDHAdv(A)).main() @ &m : res].
proof.
(* COMPLETE THIS *)
    byequiv => //.
    proc; inline *.
    swap{1} 7 -5.
    wp.
    call (_: ={arg, glob A} ==> ={res}).
    by sim.
    wp; rnd.
    call (_: ={arg, glob A} ==> ={res, glob A}).
    by sim.
    wp; rnd; rnd; skip => />; smt(expM).
qed.

  local module Gb = {
    proc main () : bool = {
      var x, y, z, m0, m1, b, b';

      x       <$ dt;
      y       <$ dt;
      (m0,m1) <@ A.choose(g ^ x);
      z       <$ dt;
      b'      <@ A.guess(g ^ y, g ^ z);
      b       <$ {0,1};
      return b' = b;
    }
  }.

  local lemma ddh1_gb &m:
      Pr[DDH1(DDHAdv(A)).main() @ &m : res] =
      Pr[Gb.main() @ &m : res].
  proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  local lemma Gb_half &m:
     Pr[Gb.main()@ &m : res] = 1%r/2%r.
  proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    byphoare=> //.
    proc.
    rnd (pred1 b').
    call Ag_ll; rnd; call Ac_ll; rnd; rnd; skip.
    move=> />; do! split; try by exact dt_ll.
    move=> b; split; first by rewrite DBool.dbool1E.
    smt(DBool.dbool1E).
  qed.

  lemma conclusion &m :
    `| Pr[CPA(ElGamal,A).main() @ &m : res] - 1%r/2%r | =
    `| Pr[DDH0(DDHAdv(A)).main() @ &m : res] -
         Pr[DDH1(DDHAdv(A)).main() @ &m : res] |.
  proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    by rewrite (cpa_ddh0 &m) -(Gb_half &m) (ddh1_gb &m).
  qed.
end section Security.

print conclusion.
