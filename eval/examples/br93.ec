(* -------------------------------------------------------------------- *)
require import AllCore List FSet FMap.
require import Distr DBool.
require (*--*) BitWord OW ROM.

(* ---------------- Sane Default Behaviours --------------------------- *)
pragma +implicits.

(* -------------------------------------------------------------------- *)
(* We start by proving Bellare and Rogaway's algorithm IND-CPA secure   *)
(* on abstract datatypes with minimal structure. We then instantiate to *)
(* semi-concrete fixed-length bitstrings (with abstract lengths).       *)
(* -------------------------------------------------------------------- *)
abstract theory BR93.
(* -------------------------------------------------------------------- *)
(* Let us consider the following abstract scenario construction. Given: *)
(* -------------------------------------------------------------------- *)

(* A set `ptxt` of plaintexts, equipped with an nilpotent addition (+^) *)
type ptxt.

op (+^): ptxt -> ptxt -> ptxt.
axiom addA p1 p2 p3: (p1 +^ p2) +^ p3 = p1 +^ (p2 +^ p3).
axiom addC p1 p2: p1 +^ p2 = p2 +^ p1.
axiom addKp p1 p2: (p1 +^ p1) +^ p2 = p2.

lemma addpK p1 p2: p1 +^ p2 +^ p2 = p1.
proof. by rewrite addC -addA addC -addA addKp. qed.

(*                    and a lossless, full, uniform distribution dptxt; *)
op dptxt: { ptxt distr |    is_lossless dptxt
                         /\ is_full dptxt
                         /\ is_uniform dptxt } as dptxt_llfuuni.
lemma dptxt_ll: is_lossless dptxt by exact/(andWl _ dptxt_llfuuni).
lemma dptxt_uni: is_uniform dptxt by have [#]:= dptxt_llfuuni.
lemma dptxt_fu: is_full dptxt by have [#]:= dptxt_llfuuni.
lemma dptxt_funi: is_funiform dptxt
by exact/(is_full_funiform dptxt_fu dptxt_uni).

(* A set `rand` of nonces, equipped with                                *)
(*                              a lossless, uniform distribution drand; *)
type rand.
op drand: { rand distr |    is_lossless drand
                         /\ is_uniform drand } as drand_lluni.
lemma drand_ll: is_lossless drand by exact/(andWl _ drand_lluni).
lemma drand_uni: is_uniform drand by exact/(andWr _ drand_lluni).

(* A set `ctxt` of ciphertexts defined as                               *)
(*                          the cartesian product of `rand` and `ptxt`; *)
type ctxt = rand * ptxt.

(* A set `pkey * skey` of keypairs, equipped with                       *)
(*                        a lossless, full, uniform distribution dkeys; *)
type pkey, skey.
op dkeys: { (pkey * skey) distr |    is_lossless dkeys
                                  /\ is_funiform dkeys } as dkeys_llfuni.
lemma dkeys_ll: is_lossless dkeys by exact/(andWl _ dkeys_llfuni).
lemma dkeys_funi: is_funiform dkeys by exact/(andWr _ dkeys_llfuni).

(* A family `f` of trapdoor permutations over `rand`,                   *)
(*       indexed by `pkey`, with inverse family `fi` indexed by `skey`; *)
op f : pkey -> rand -> rand.
op fi: skey -> rand -> rand.
axiom fK pk sk x: (pk,sk) \in dkeys => fi sk (f pk x) = x.

lemma fI pk x y: (exists sk, (pk,sk) \in dkeys) =>
  f pk x = f pk y => x = y.
proof. by move=> [sk] + fx_eq_fy - /fK ^ /(_ x) <- /(_ y) <-; congr. qed.

(* A random oracle from `rand` to `ptxt`, modelling a hash function H;  *)
(* (we simply instantiate the generic theory of Random Oracles with     *)
(*    the types and output distribution declared above, discharging all *)
(*          assumptions on the instantiated parameters--there are none) *)
clone import ROM as H with
  type in_t    <- rand,
  type out_t   <- ptxt,
  type d_in_t  <- unit,
  type d_out_t <- bool,
  op   dout _  <- dptxt.
import H.Lazy.

(* We can define the Bellare-Rogaway 93 PKE Scheme.                     *)
(* BR93 is a module that, given access to an oracle H from type         *)
(*   `from` to type `rand` (see `print Oracle.`), implements procedures *)
(*   `keygen`, `enc` and `dec` as follows described below.              *)
module BR93 (H : Oracle) = {
  (* `keygen` simply samples a key pair in `dkeys` *)
  proc keygen() = {
    var kp;

    kp <$ dkeys;
    return kp;
  }

  (* `enc` samples a random string `r` in `drand` and uses it to       *)
  (*   produce a random mask `h` using the hash function, then returns *)
  (*      the image of `r` by permutation `f` and the plaintext masked *)
  (*                                                         with `h`. *)
  proc enc(pk, m) = {
    var r, h;

    r <$ drand;
    h <@ H.o(r);
    return (f pk r,h +^ m);
  }

  (* `dec` parses its input as a nonce `r` and a masked plaintext `m` *)
  (*  before recovering the original random string from `r` using the *)
  (*      inverse permutation `fi` and computing its image `h` by the *)
  (*  random oracle. The original plaintext is recovered by unmasking *)
  (*                                                    `m` with `h`. *)
  proc dec(sk, c) = {
    var r, h, m;

    (r,m) <- c;
    r     <- fi sk r;
    h     <@ H.o(r);
    return h +^ m;
  }
}.

(* We can quickly prove it correct as a sanity check.                 *)
section Correctness.
local module Correctness = {
  proc main(m) = {
    var pk, sk, c, m';

    (pk,sk) <@ BR93(LRO).keygen();
    c       <@ BR93(LRO).enc(pk,m);
    m'      <@ BR93(LRO).dec(sk,c);
    return (m = m');
  }
}.

local lemma BR93_correct &m m: Pr[Correctness.main(m) @ &m: res] = 1%r.
proof.
byphoare=> //; conseq (: _ ==> true) (: _ ==> res)=> //.
+ proc; inline *.
  rcondf 17.
  + auto=> /> &hr [pk sk] kp_in_dkeys r _ y _ /=.
    rewrite fK //; split=> [_ _ _|-> //].
    by rewrite mem_set.
  auto=> /> &hr [pk sk] kp_in_dkeys r _ y _ /=.
  rewrite fK //; split=> [_ y' _|].
  + by rewrite get_set_sameE -addA addKp.
  rewrite domE; case: (LRO.m{hr}.[r])=> [|p] //= _ _.
  by rewrite -addA addKp.
by proc; inline *; auto=> />; rewrite dkeys_ll drand_ll dptxt_ll.
qed.
end section Correctness.

(* However, what we are really interested in is proving that it is      *)
(* IND-CPA secure if `f` is a one-way trapdoor permutation.             *)

(* We use cloning to get definitions for OWTP security                  *)
clone import OW as OW_rand with
  type D           <- rand,
  type R           <- rand,
  type pkey        <- pkey,
  type skey        <- skey,
  op   dkeys       <- dkeys,
  op   challenge _ <- drand,
  op   f           <- f,
  op   finv        <- fi
proof *.
(* proof dkeys_ll, finvof, challenge_ll, challenge_uni. *)
realize dkeys_ll by exact/dkeys_ll.
realize challenge_ll by move=> _ _; exact/drand_ll.
realize challenge_uni by move=> _ _; exact/drand_uni.
realize finvof by move=> pk sk x /fK ->.
realize finv_correct.
proof.
  move=> pk sk y h.
  have hp : valid_pkey pk by exists sk.
  by move=> /(_ hp) [] x [ ? ->]; rewrite fK.
qed.
realize fofinv.
proof.
  move=> pk sk x h.
  have hp : valid_pkey pk by exists sk.
  by move=> /(_ hp) [ y [ ? ->]]; rewrite fK.
qed.

(* But we can't do it (yet) for IND-CPA because of the random oracle    *)
(*             Instead, we define CPA for BR93 with that particular RO. *)
module type Adv (ARO : POracle)  = {
  proc a1(p:pkey): (ptxt * ptxt)
  proc a2(c:ctxt): bool
}.

(* We need to log the random oracle queries made to the adversary       *)
(*                               in order to express the final theorem. *)
module Log (H : Oracle) = {
  var qs: rand list

  proc init() = {
    qs <- [];
          H.init();
  }

  proc o(x) = {
    var r;

    qs <- x::qs;
    r  <@ H.o(x);
    return r;
  }
}.

module BR93_CPA(A:Adv) = {
  proc main(): bool = {
    var pk, sk, m0, m1, c, b, b';

                Log(LRO).init();
    (pk,sk)  <@ BR93(LRO).keygen();
    (m0,m1)  <@ A(Log(LRO)).a1(pk);
    b        <$ {0,1};
    c        <@ BR93(LRO).enc(pk,b?m0:m1);
    b'       <@ A(Log(LRO)).a2(c);
    return b' = b;
  }
}.

(* We want to prove the following:                                      *)
(*   forall (valid) CPA adversary A which makes at most q queries to H, *)
(*     there exists a OW adversary I such that                          *)
(*          `|Pr[BR_CPA(A): res] - 1/2| <= Pr[OW_f(I): res]             *)
(* We construct I as follows, using A.a1 and A.a2 as black boxes        *)
module I(A:Adv): Inverter = {
  var x:rand

  proc invert(pk:pkey,y:rand): rand = {
    var m0, m1, h, b;

               Log(LRO).init();
    (m0,m1) <@ A(Log(LRO)).a1(pk);
    h       <$ dptxt;
    b       <@ A(Log(LRO)).a2(y,h);
    x       <- nth witness Log.qs (find (fun p => f pk p = y) Log.qs);

    return x;
  }
}.

(* We now prove the result using a sequence of games                    *)
section.
(* All lemmas in this section hold for all (valid) CPA adversary A      *)
declare module A <: Adv { -LRO, -Log }.

declare axiom A_a1_ll (O <: POracle {-A}): islossless O.o => islossless A(O).a1.
declare axiom A_a2_ll (O <: POracle {-A}): islossless O.o => islossless A(O).a2.

(* Step 1: replace RO call with random sampling                         *)
local module Game1 = BR93_CPA(A) with {
  var r : rand

  proc main [
    (* new local variable to store the sampled ptxt *)
    var h : ptxt
    (* inline key generation *)
    ^ <@ {2} ~ { (pk, sk) <$ dkeys; }
    (* inline challenge encryption and idealize RO call *)
    ^ c<@ ~ { r <$ drand; h <$ dptxt; c <- (f pk r, h +^ (b ? m0 : m1)); }
  ]
}.

local lemma pr_Game0_Game1 &m:
     Pr[BR93_CPA(A).main() @ &m: res]
  <=   Pr[Game1.main() @ &m: res]
     + Pr[Game1.main() @ &m: Game1.r \in Log.qs].
proof.
(* COMPLETE THIS *)
  have h1: Pr[BR93_CPA(A).main() @ &m : res] <= Pr[Game1.main() @ &m : res \/ Game1.r \in Log.qs]. 
  + byequiv (_: ={glob A} ==> res{1} => res{2} \/ (Game1.r \in Log.qs){2})=> //=. proc. 
  inline LRO.o. call (_: Game1.r \in Log.qs, ={Log.qs} /\ eq_except (pred1 Game1.r{2}) LRO.m{1} LRO.m{2}). 
  exact/A_a2_ll. proc; inline *; auto=> />; smt(eq_except_set_eq eq_exceptP get_setE mem_set). 
  by move=> &2 _; proc; inline *; auto; smt(dptxt_ll). by move=> _; proc; inline *; auto; smt(dptxt_ll). 
  inline *. swap{1} 9 -3. swap{1} 11 -4. swap{2} 5 2.
  wp. rnd. rnd. rnd. 
  call (_: ={glob Log, glob LRO} /\ (forall x, x \in LRO.m => x \in Log.qs){1}). 
  proc; inline *; auto=> />; smt(mem_set domE get_setE). 
  inline *; auto=> />; smt(get_set_sameE eq_except_setl emptyE). 
  have h2: Pr[Game1.main() @ &m : res \/ (Game1.r \in Log.qs)] <= Pr[Game1.main() @ &m : res] + Pr[Game1.main() @ &m : Game1.r \in Log.qs]. 
    + rewrite Pr[mu_or]; smt(mu_bounded). 
  smt().
qed.

(* Step 2: replace h ^ m with h in the challenge encryption            *)
local module Game2 = Game1 with {
  proc main [
    (* Challenge ciphertext is now produced uniformly at random *)
    ^ c<- ~ { c <- (f pk r, h); }
  ]
}.

local equiv eq_Game1_Game2: Game1.main ~ Game2.main:
  ={glob A} ==> ={glob Log, res} /\ Game1.r{1} = Game2.r{2}.
proof.
(* COMPLETE THIS *)
  proc. call (_: ={glob Log, glob LRO}). by proc; inline *; auto. wp. rnd (fun x => x +^ (if b then m0 else m1)){2}. rnd. auto. call (_: ={glob Log, glob LRO}). by proc; inline *; auto. inline *; auto=> />; smt(addpK dptxt_fu dptxt_funi dptxt_uni).
qed.

local lemma pr_Game1_Game2 &m:
  Pr[Game1.main() @ &m: res] = Pr[Game2.main() @ &m: res].
proof. by byequiv eq_Game1_Game2. qed.

local lemma pr_bad_Game1_Game2 &m:
    Pr[Game1.main() @ &m: Game1.r \in Log.qs]
  = Pr[Game2.main() @ &m: Game2.r \in Log.qs].
proof. by byequiv eq_Game1_Game2. qed.

local lemma pr_Game2 &m: Pr[Game2.main() @ &m: res] = 1%r / 2%r.
proof.
byphoare=> //=; proc.
swap 4 4.
wp; rnd (pred1 b')=> //=.
inline *; call (_: true).
+ exact A_a2_ll. (* adversary *)
+ by proc; call (LRO_o_ll _); auto=> /=; apply: dptxt_ll. (* oracle *)
auto; call (_: true).
+ exact A_a1_ll. (* adversary *)
+ by proc; call (LRO_o_ll _); auto=> /=; apply: dptxt_ll. (* oracle *)
auto=> />; rewrite dkeys_ll drand_ll dptxt_ll /predT /=.
by move=> _ _ _ _ _ _ r; rewrite dbool1E pred1E.
qed.

(* Step 3: The reduction step -- if A queries the RO with the randomness *)
(*     used to encrypt the challenge, then I(A) inverts the OW challenge *)
(* We need a version of the one-way game where the challenge is a global *)
local module OWr (I : Inverter) = {
  var x : rand

  proc main() : bool = {
    var x', pk, sk;

    (pk,sk) <$ dkeys;
    x       <$ drand;
    x'      <@ I.invert(pk,f pk x);
    return (x = x');
  }
}.

(* We can easily prove that it is strictly equivalent to OW              *)
local lemma OW_OWr &m (I <: Inverter {-OWr}):
    Pr[OW(I).main() @ &m: res]
  = Pr[OWr(I).main() @ &m: res].
proof. by byequiv=> //=; sim. qed.

local lemma pr_Game2_OW &m:
     Pr[Game2.main() @ &m: Game2.r \in Log.qs]
  <= Pr[OW(I(A)).main() @ &m: res].
proof.
  (* COMPLETE THIS *)
  rewrite (OW_OWr &m (I(A))).
  byequiv=> //=. proc. inline *.
  swap{1} 3 -2. wp.
  call (_: ={glob Log, glob LRO}). + proc; inline *; auto.
  swap{2} 4 3. swap{2} 2 4. swap{1} 5 3.
  rnd{1}. wp. rnd. wp. rnd.
  call (_: ={glob Log, glob LRO}). + proc; inline *; auto.
  wp. rnd. auto. progress.
  have h1: has (fun p => f pkskL.`1 p = f pkskL.`1 rL) qs_R0.
  + rewrite List.hasP; exists rL. smt().
  smt(nth_find fI).
qed.

lemma Reduction &m:
     Pr[BR93_CPA(A).main() @ &m : res] - 1%r/2%r
  <= Pr[OW(I(A)).main() @ &m: res].
proof.
(* COMPLETE THIS *)
  smt(pr_Game0_Game1 pr_Game1_Game2 pr_bad_Game1_Game2 pr_Game2 pr_Game2_OW).
qed.
end section.
end BR93.

(* We now consider a concrete instance:                                 *)
(*   - plaintexts are bitstrings of length k > 0                        *)
(*   - nonces are bitstrings of length l > 0                            *)
(*   - ciphertexts are bitstrings of length n = k + l                   *)

(* Plaintexts                                                           *)
op k : { int | 0 < k } as gt0_k.

clone import BitWord as Plaintext with
  op n <- k
proof gt0_n by exact/gt0_k
rename
  "word" as "ptxt"
  "dunifin" as "dptxt".
import DWord.

(* Nonces                                                               *)
op l : { int | 0 < l } as gt0_l.

clone import BitWord as Randomness with
  op n <- l
proof gt0_n by exact/gt0_l
rename
  "word" as "rand"
  "dunifin" as "drand".
import DWord.

(* Ciphertexts                                                          *)
op n = l + k.
lemma gt0_n: 0 < n by smt(gt0_k gt0_l).

clone import BitWord as Ciphertext with
  op n <- n
proof gt0_n by exact/Self.gt0_n
rename "word" as "ctxt".

(* Parsing and Formatting                                               *)
op (||) (r:rand) (p:ptxt) : ctxt = mkctxt ((ofrand r) ++ (ofptxt p)).
op parse (c:ctxt): rand * ptxt =
  (mkrand (take l (ofctxt c)),mkptxt (drop l (ofctxt c))).

lemma parseK r p: parse (r || p) = (r,p).
proof.
rewrite /parse /(||) ofctxtK 1:size_cat 1:size_rand 1:size_ptxt //=.
by rewrite take_cat drop_cat size_rand take0 drop0 cats0 /= mkrandK mkptxtK.
qed.

lemma formatI (r : rand) (p : ptxt) r' p':
  (r || p) = (r' || p') => (r,p) = (r',p').
proof. by move=> h; rewrite -(@parseK r p) -(@parseK r' p') h. qed.

(* A set `pkey * skey` of keypairs, equipped with                       *)
(*                         a lossless, full, uniform distribution dkeys *)
type pkey, skey.
op dkeys: { (pkey * skey) distr |    is_lossless dkeys
                                  /\ is_funiform dkeys } as dkeys_llfuni.

(* A family `f` of trapdoor permutations over `rand`,                   *)
(*        indexed by `pkey`, with inverse family `fi` indexed by `skey` *)
op f : pkey -> rand -> rand.
op fi: skey -> rand -> rand.
axiom fK pk sk x: (pk,sk) \in dkeys => fi sk (f pk x) = x.

(* Random Oracle                                                        *)
clone import ROM as H with
  type in_t    <- rand,
  type out_t   <- ptxt,
  type d_in_t  <- unit,
  type d_out_t <- bool,
  op   dout _  <- dptxt.
import Lazy.

(* A Definition for OWTP Security                                       *)
module type Inverter = {
  proc invert(pk:pkey, x:rand): rand
}.

module Exp_OW (I : Inverter) = {
  proc main(): bool = {
    var pk, sk, x, x';

    (pk,sk) <$ dkeys;
    x       <$ drand;
    x'      <@ I.invert(pk,f pk x);
    return (x = x');
  }
}.

(* A Definition for CPA Security                                        *)
module type Scheme (RO : Oracle) = {
  proc keygen(): (pkey * skey)
  proc enc(pk:pkey, m:ptxt): ctxt
}.

module type Adv (ARO : POracle)  = {
  proc a1(p:pkey): (ptxt * ptxt)
  proc a2(c:ctxt): bool
}.

module CPA (O : Oracle) (S:Scheme) (A:Adv) = {
  proc main(): bool = {
    var pk, sk, m0, m1, c, b, b';

               O.init();
    (pk,sk) <@ S(O).keygen();
    (m0,m1) <@ A(O).a1(pk);
    b       <$ {0,1};
    c       <@ S(O).enc(pk,b?m0:m1);
    b'      <@ A(O).a2(c);
    return b' = b;
  }
}.

(* And a definition for the concrete Bellare-Rogaway Scheme             *)
module (BR : Scheme) (H : Oracle) = {
  proc keygen():(pkey * skey) = {
    var pk, sk;

    (pk,sk) <$ dkeys;
    return (pk,sk);
  }

  proc enc(pk:pkey, m:ptxt): ctxt = {
    var h, r;

    r <$ drand;
    h <@ H.o(r);
    return ((f pk r) || m +^ h);
  }

  proc dec(sk:skey, c:ctxt): ptxt = {
    var r, p, h;

    (r,p) <- parse c;
    r     <- fi sk r;
    h     <@ H.o(r);
    return p +^ h;
  }
}.

(* And our inverter                                                     *)
module I (A:Adv) (H : Oracle) = {
  var qs : rand list

  module QRO = {
    proc o(x:rand) = {
      var r;

      qs <- x::qs;
      r  <@ H.o(x);
      return r;
    }
  }

  proc invert(pk:pkey,y:rand): rand = {
    var x, m0, m1, h, b;

    qs      <- [];
               H.init();
    (m0,m1) <@ A(QRO).a1(pk);
    h       <$ dptxt;
    b       <@ A(QRO).a2(y || h);
    x       <- nth witness qs (find (fun p => f pk p = y) qs);

    return x;
  }
}.

(* We will need to turn a concrete CPA adversary into an abstract one.  *)
(*      We do not need to do it for the inverter as the types coincide. *)
module A_CPA (A : Adv) (H : POracle) = {
  proc a1 = A(H).a1

  proc a2(c:rand * ptxt): bool = {
    var b;

    b <@ A(H).a2(c.`1 || c.`2);
    return b;
  }
}.

section.
declare module A <: Adv { -LRO, -I }.

declare axiom A_a1_ll (O <: POracle {-A}): islossless O.o => islossless A(O).a1.
declare axiom A_a2_ll (O <: POracle {-A}): islossless O.o => islossless A(O).a2.

local clone import BR93 as Instance with
  type pkey  <- pkey,
  type skey  <- skey,
  op   dkeys <- dkeys,
  op   f     <- f,
  op   fi    <- fi,
  type ptxt  <- ptxt,
  op   (+^)  <- Plaintext.(+^),
  op   dptxt <- dptxt,
  type rand  <- rand,
  op   drand <- drand
proof *.
realize addA          by move=> p1 p2 p3; algebra.
realize addC          by move=> p1 p2; algebra.
realize addKp         by move=> p1 p2; algebra.
realize dptxt_llfuuni by smt(@Plaintext.DWord).
realize drand_lluni   by smt(@Randomness.DWord).
realize dkeys_llfuni  by exact/dkeys_llfuni.
realize fK            by exact/fK.

lemma Reduction &m:
     Pr[CPA(LRO, BR, A).main() @ &m : res] - 1%r / 2%r
  <= Pr[Exp_OW(Self.I(A, LRO)).main() @ &m : res].
proof.
(* COMPLETE THIS *)
  smt(pr_Game0_Game1 pr_Game1_Game2 pr_bad_Game1_Game2 pr_Game2 pr_Game2_OW).
qed.

end section.