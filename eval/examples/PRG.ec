(* -------------------------------------------------------------------- *)
require import AllCore List Distr FSet FMap.
require import IntDiv Mu_mem StdRing StdOrder StdBigop.
(*---*) import Bigint Ring.IntID RField IntOrder RealOrder BIA.
require (*--*) FinType.

(* ---------------- Sane Default Behaviours --------------------------- *)
pragma +implicits.

(* -------------------------------------------------------------------- *)
(** A finite type of seeds equipped with its uniform distribution **)
clone include MFinite
rename
  [type] "t" as "seed"
  "dunifin" as "dseed"
  "duniform" as "dseed".

(* -------------------------------------------------------------------- *)
(** Some output type equipped with some lossless distribution **)
type output.
op dout: { output distr | is_lossless dout } as dout_ll.
hint exact random: dout_ll.

(* -------------------------------------------------------------------- *)
(** We use a public RF that, on input a seed, produces a seed and
    an output...                                                        *)
module type RF = {
  proc init() : unit
  proc f(x:seed): seed * output
}.

(** ...to build a PRG that produces random outputs... **)
(** We let our PRG have internal state, which we need to initialize **)
module type PRG = {
  proc init(): unit
  proc prg()   : output
}.

(* -------------------------------------------------------------------- *)
(** Distinguishers can call
  *   - the PRG at most qP times, and
  *   - the PRF at most qF times, and
  *   - return a boolean *)
op qP : { int | 0 <= qP } as ge0_qP.
op qF : { int | 0 <= qF } as ge0_qF.

module type ARF = {
  proc f(_:seed): seed * output
}.

module type APRG = {
  proc prg(): output
}.

module type Adv (F:ARF) (P:APRG) = {
  proc a(): bool
}.

module Exp (A:Adv) (F:RF) (P:PRG) = {
  module A = A(F,P)

  proc main():bool = {
    var b: bool;

         F.init();
         P.init();
    b <@ A.a();
    return b;
  }
}.

(** A PRG is secure iff it is indistinguishable from sampling in $dout
    by an adversary with access to the PRF and the PRG interfaces *)
module PrgI = {
  proc init () : unit = { }

  proc prg(): output = {
    var r;

    r <$ dout;
    return r;
  }
}.
(* Adv^PRG_A,F,P = `| Exp(A,F,P) - Exp(A,F,PrgI) | *)

(* -------------------------------------------------------------------- *)
(* Concrete considerations                                              *)

(* We use the following RF *)
module F = {
  var m:(seed,seed * output) fmap

  proc init(): unit = {
     m <- empty;
  }

  proc f (x:seed) : seed * output = {
    var r1, r2;

    r1 <$ dseed;
    r2 <$ dout;
    if (x \notin m)
      m.[x] <- (r1,r2);

    return oget (m.[x]);
  }
}.

lemma FfL: islossless F.f.
proof. islossless. qed.

(* And we are proving the security of the following PRG *)
module P (F:RF) = {
  var seed: seed
  var logP: seed list

  proc init(): unit = {
    seed <$ dseed;
  }

  proc prg(): output = {
    var r;

    (seed,r) <@ F.f (seed);
    return r;
  }
}.

(* -------------------------------------------------------------------- *)
(* We use the following oracle in an intermediate game that links two
   sections.                                                            *)

module Psample = {
  proc init(): unit = {
    P.seed <$ dseed;
    P.logP <- [];
  }

  proc prg(): output = {
    var r1, r2;

    r1     <$ dseed;
    r2     <$ dout;
    P.logP <- P.seed :: P.logP;
    P.seed <- r1;
    return r2;
  }
}.

lemma PsampleprgL: islossless Psample.prg.
proof. islossless. qed.

(* -------------------------------------------------------------------- *)
(* In preparation of the eager/lazy reasoning step                      *)
(* -------------------------------------------------------------------- *)
module Resample = {
  proc resample() : unit = {
    var n, r;

    n      <- size P.logP;
    P.logP <- [];
    P.seed <$ dseed;
    while (size P.logP < n) {
      r      <$ dseed;
      P.logP <- r :: P.logP;
    }
  }
}.

module Exp'(A:Adv) = {
  module A = A(F,Psample)

  proc main():bool = {
    var b : bool;
         F.init();
         Psample.init();
    b <@ A.a();
         Resample.resample();
    return b;
  }
}.

(* The Proof                                                            *)

section.
  (* Forall Adversary A that does not share memory with P or F... *)
  declare module A <: Adv {-P,-F}.

  (* ... and whose a procedure is lossless whenever F.f and P.prg are *)
  declare axiom AaL (F <: ARF {-A}) (P <: APRG {-A}):
    islossless P.prg =>
    islossless F.f =>
    islossless A(F,P).a.

  (* We show that the adversary can distinguish P from Psample only
     when P.prg is called twice with the same input. *)

  (* First, we add some logging so we can express the bad event *)
  local module Plog = {
    proc init(): unit = {
      P.seed <$ dseed;
      P.logP <- [];
    }

    proc prg(): output = {
      var r;

      P.logP     <- P.seed :: P.logP;
      (P.seed,r) <@ F.f(P.seed);
      return r;
    }
  }.

  local lemma PlogprgL: islossless Plog.prg.
  proof. by proc; call FfL; wp. qed.

  local lemma P_Plog &m:
    Pr[Exp(A,F,P(F)).main() @ &m: res] = Pr[Exp(A,F,Plog).main() @ &m: res].
  proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  byequiv=> //.
  proc.
  call (_: ={P.seed, glob F}).
  by sim.
  by sim.
  inline *; auto.
qed.

  (* Bad holds whenever:
   *  - there is a cycle in the state, OR
   *  - an adversary query collides with an internal seed. *)
  inductive Bad logP (m : ('a,'b) fmap) =
    | Cycle of (!uniq logP)
    | Collision r of (mem logP r) & (r \in m).

  lemma negBadE logP (m : ('a,'b) fmap):
    !Bad logP m <=>
      (uniq logP /\ forall r, !mem logP r \/ r \notin m).
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  split.
  move=> nbad; split.
  case: (uniq logP) => //.
  by move=> h; apply nbad; apply/Cycle.
  move=> r; case: (r \in logP) => //=.
  by move=> h_mem; apply/negP => h_in; apply nbad; exact (Collision r h_mem h_in).
  move=> [h_uniq h_disj]; apply/negP => h_bad; case: h_bad.
  by rewrite h_uniq.
  by move=> r h_mem h_in; move: (h_disj r); rewrite h_mem h_in.
qed.

  (* In this game, we replace the PRF queries with fresh sampling operations *)
  inductive inv (m1 m2 : ('a,'b) fmap) (logP : 'a list) =
    | Invariant of
          (forall r, r \in m1 <=> (r \in m2 \/ mem logP r))
        & (forall r, r \in m2 => m1.[r] = m2.[r]).

  local lemma Plog_Psample &m:
    Pr[Exp(A,F,Plog).main() @ &m: res] <=
      Pr[Exp(A,F,Psample).main() @ &m: res] +
      Pr[Exp(A,F,Psample).main() @ &m: Bad P.logP F.m].
proof.
(* COMPLETE THIS *)
  byequiv (_: ={glob A} ==> res{1} => res{2} \/ Bad P.logP{2} F.m{2})=> //.
  proc.
  call (_: Bad P.logP F.m, ={P.seed, P.logP} /\ inv F.m{1} F.m{2} P.logP{2}).
  exact AaL.
  proc.
  inline F.f.
  swap{1} 3 -2.
  swap{1} 4 -2.
  wp.
  rnd.
  rnd.
  skip.
  progress.
  smt(get_set_sameE).
  smt(get_set_sameE).
  apply Invariant.
  move: H0 => [h_dom h_val] r0.
  smt(mem_set).
  move: H0 => [h_dom h_val] r0 h_in.
  smt(get_setE negBadE).
  move: H0 => [h_dom h_val].
  smt(negBadE).
  move: H0 => [h_dom h_val].
  smt(negBadE).
  move: H0 => [h_dom h_val].
  smt(negBadE).
  move=> &2 _; exact PlogprgL.
  move=> _; proc; auto.
  move=> &2 [[h_bad _] _]; split; first smt(dseed_ll).
  move=> _ v _; rewrite /predT /=.
  split; first smt(dout_ll).
  move=> _ v0 _; case: h_bad => [h_nuniq | r h_mem h_in].
  apply Cycle; smt.
  apply (Collision r); smt.
  proc.
  auto.
  progress.
  smt(get_set_sameE).
  move: H0 => [h_dom h_val]; apply Invariant => r.
  smt(mem_set).
  smt(get_setE).
  move: H0 => [h_dom h_val].
  smt(negBadE mem_set).
  move: H0 => [h_dom h_val].
  smt(negBadE mem_set).
  move: H0 => [h_dom h_val].
  smt().
  move: H0 => [h_dom h_val].
  smt().
  move: H0 => [h_dom h_val].
  smt().
  move=> &2 _; exact FfL.
  move=> _; proc; auto.
  move=> &2 [[h_bad _] _]; split; first smt(dseed_ll).
  move=> _ v h_v; rewrite /predT /=.
  split.
  exact dout_ll.
  move=> _ v0 h_v0; case: (x{2} \notin F.m{2}) => h_x.
  case: h_bad => [? | r ??]; [apply Cycle; assumption | apply (Collision r); smt(mem_set)].
  assumption.
  inline *.
  auto.
  progress.
  apply Invariant; smt(emptyE mem_empty).
  smt().
  smt().
qed.

  local lemma Psample_PrgI &m:
    Pr[Exp(A,F,Psample).main() @ &m: res] = Pr[Exp(A,F,PrgI).main() @ &m: res].
  proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  admit.
  qed.

  local lemma Resample_resampleL: islossless Resample.resample.
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  proc.
  while (true) (n - size P.logP).
  auto => />; smt(dseed_ll size_ge0).
  auto => />; smt(dseed_ll size_ge0).
qed.

  local module Exp'A = Exp'(A).

  local lemma ExpPsample_Exp' &m:
      Pr[Exp(A,F,Psample).main() @ &m: Bad P.logP F.m]
    = Pr[Exp'(A).main() @ &m: Bad P.logP F.m].
  proof.
    (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
    admit.
  qed.

  lemma P_PrgI &m:
    Pr[Exp(A,F,P(F)).main() @ &m: res] <=
      Pr[Exp(A,F,PrgI).main() @ &m: res] + Pr[Exp'(A).main() @ &m: Bad P.logP F.m].
  proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  rewrite (P_Plog &m) -(ExpPsample_Exp' &m) -(Psample_PrgI &m).
  exact (Plog_Psample &m).
  qed.
end section.

(* -------------------------------------------------------------------- *)

(* We now bound Pr[Exp(A,F,Psample).main() @ &m: Bad Plog.logP F.m] *)

(* For now, we use the following counting variant of the adversary to
   epxress the final result. Everything up to now applies to
   non-counting adversaries, but we need the counting to bound the
   probability of Bad. *)

module C (A:Adv,F:ARF,P:APRG) = {
  var cF, cP:int

  module CF = {
    proc f(x): seed * output = {
      var r <- witness;

      if (cF < qF) { cF <- cF + 1; r <@ F.f(x);}
      return r;
    }
  }

  module CP = {
    proc prg (): output = {
      var r <- witness;

      if (cP < qP) { cP <- cP + 1; r <@ P.prg();}
      return r;
    }
  }

  module A = A(CF,CP)

  proc a(): bool = {
    var b:bool;

    cF <- 0;
    cP <- 0;
    b <@ A.a();
    return b;
  }
}.

lemma CFfL (A <: Adv) (F <: ARF) (P <: APRG):
  islossless F.f =>
  islossless C(A,F,P).CF.f.
proof. by move=> FfL; proc; sp; if=> //; call FfL; wp. qed.

lemma CPprgL (A <: Adv) (F <: ARF) (P <: APRG):
  islossless P.prg =>
  islossless C(A,F,P).CP.prg.
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
by move=> PprgL; proc; sp; if=> //; call PprgL; wp.
qed.

lemma CaL (A <: Adv {-C}) (F <: ARF {-A}) (P <: APRG {-A}):
  (forall (F <: ARF {-A}) (P <: APRG {-A}),
    islossless P.prg => islossless F.f => islossless A(F,P).a) =>
     islossless F.f
  => islossless P.prg
  => islossless C(A,F,P).a.
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
move=> AaL FfL PprgL; proc.
call (AaL (<:C(A,F,P).CF) (<:C(A,F,P).CP) _ _).
+ by apply (CPprgL A F P PprgL).
+ by apply (CFfL A F P FfL).
by auto.
qed.

section.
  declare module A <: Adv {-C,-P,-F}.
  declare axiom AaL (F <: ARF {-A}) (P <: APRG {-A}):
    islossless P.prg =>
    islossless F.f =>
    islossless A(F,P).a.

  lemma pr &m:
    Pr[Exp(C(A),F,P(F)).main() @ &m: res] <=
        Pr[Exp(C(A),F,PrgI).main() @ &m: res]
      + Pr[Exp'(C(A)).main() @ &m: Bad P.logP F.m].
  proof.
  apply (P_PrgI (<: C(A)) _ &m).
  + move=> F0 P0 F0fL P0prgL; apply (CaL A F0 P0) => //.
    by apply AaL.
  qed.

  lemma pr_newbad (log : seed list) (m : (seed, seed * output) fmap):
       !Bad log m
    => mu dseed (fun x=> Bad (x :: log) m) = (card (fdom m) + size log)%r / Support.card%r.
  proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  admit.
  qed.

  local lemma Bad_bound:
    phoare [Exp'(C(A)).main : true ==>
      Bad P.logP F.m] <= ((qP * qF + (qP - 1) * qP %/ 2)%r / Support.card%r).
  proof.
  proc.
  seq 3: true
         1%r ((qP * qF + (qP - 1) * qP %/ 2)%r / Support.card%r)
         0%r 1%r
         (size P.logP <= qP /\ card (fdom F.m) <= qF)=> //.
  + inline Exp'(C(A)).A.a; wp.
    call (_: size P.logP = C.cP /\ C.cP <= qP /\
             card (fdom F.m) <= C.cF /\ C.cF <= qF).
    (* prg *)
    + proc; sp; if=> //.
      call (_: size P.logP = C.cP - 1 ==> size P.logP = C.cP).
      + by proc; auto=> /#.
      by auto=> /#.
    (* f *)
    proc; sp; if=> //.
    call (_: card (fdom F.m) < C.cF ==> card (fdom F.m) <= C.cF).
    proc; auto=> /> &hr h r1 _ r2 _.
    + by rewrite fdom_set fcardU fcard1; smt w=fcard_ge0.
    by auto=> /#.
  + inline *; auto=> />.
    by rewrite fdom0 fcards0 /=; smt w=(ge0_qP ge0_qF).
  inline Resample.resample.
  exists* P.logP; elim* => logP.
  seq 3: true
         1%r  ((qP * qF + (qP - 1) * qP %/ 2)%r / Support.card%r)
         0%r 1%r
         (n = size logP /\ n <= qP /\ P.logP = [] /\
          card (fdom F.m) <= qF)=> //.
  + by rnd; wp.
  conseq (_ : _ : <= (if Bad P.logP F.m then 1%r else
      (sumid (qF + size P.logP) (qF + n))%r / Support.card%r)).
  + move=> /> &hr.
    have /= -> /= szlog_le_qP szm_le_qF := negBadE A AaL [] F.m{hr}.
    apply/ler_wpmul2r; first smt w=Support.card_gt0. apply/le_fromint.
    rewrite -{1}(@add0z qF) big_addn /= /predT -/predT.
    rewrite (@addzC qF) !addrK big_split big_constz.
    rewrite count_predT size_range /= ler_maxr ?size_ge0 addrC.
    rewrite ler_add 1:mulrC ?ler_wpmul2r // ?ge0_qF.
    rewrite sumidE ?size_ge0 leq_div2r // mulrC.
    move: (size_ge0 logP) szlog_le_qP => /IntOrder.ler_eqVlt [<- /#|gt0_sz le].
    by apply/IntOrder.ler_pmul => // /#.
  while (n <= qP /\ card (fdom F.m) <= qF).
  + move=> Hw; exists* P.logP, F.m; elim* => logPw m.
    case: (Bad P.logP F.m).
    + by conseq (_ : _ : <= (1%r))=> // /#.
    seq 2: (Bad P.logP F.m)
           ((qF + size logPw)%r / Support.card%r) 1%r 1%r
           ((sumid (qF + (size logPw + 1)) (qF + n))%r / Support.card%r)
           (F.m = m /\ r::logPw = P.logP /\
            n <= qP /\ card (fdom F.m) <= qF)=> //.
    + by wp; rnd=> //.
    + wp; rnd; auto=> /> &0 _ /le_fromint domF_le_qF _ /pr_newbad ->.
      apply: ler_wpmul2r.
      + by apply: invr_ge0; smt(Support.card_gt0).
      by rewrite !fromintD ler_add2r.
    + conseq Hw; progress=> //.
      by rewrite H1 /= (Ring.IntID.addrC 1) lerr.
    progress=> //; rewrite H2 /= -mulrDl addrA -fromintD.
    rewrite
      (@BIA.big_cat_int (qF + size P.logP{hr} + 1) (_ + List.size _))
      ?BIA.big_int1 /#.
  by skip; progress=> /#.
  qed.

  lemma conclusion &m:
    Pr[Exp(C(A),F,P(F)).main() @ &m: res] <=
        Pr[Exp(C(A),F,PrgI).main() @ &m: res]
      + (qP * qF + (qP - 1) * qP %/ 2)%r / Support.card%r.
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  apply (ler_trans (Pr[Exp(C(A), F, PrgI).main() @ &m : res] + Pr[Exp'(C(A)).main() @ &m : Bad P.logP F.m])).
  apply (pr &m).
  apply ler_add2l.
  byphoare Bad_bound => //.
qed.
end section.
