require import Int Real Distr List FSet.
require import DInterval Dexcepted.

pragma +implicits.

clone WhileSamplingFixedTest as D4_6 with
  type t             <- int,
  type input         <- unit,
  op   dt   (i:unit) <- [1..6],
  op   test (i:unit) <- fun r=> !1 <= r <= 4
proof *.

module D4 = {
  proc sample () : int = {
    var r : int;

    r <$ [1..4];
    return r;
  }
}.

lemma prD4 : forall k &m, Pr[D4.sample() @ &m : res = k] =
  if 1 <= k <= 4 then 1%r/4%r else 0%r.
proof.
move=> k &m; byphoare=> //.
by proc; rnd; auto=> />; rewrite dinter1E.
qed.

module D6 = {
  proc sample () : int = {
    var r <- 5;

    while (5 <= r) r <$ [1..6];
    return r;
  }
}.

equiv D4_Sample: D4.sample ~ D4_6.SampleE.sample: true ==> ={res}.
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  proc; rnd; skip=> />.
  split=> [r hr|_ r hr].
  + rewrite dexcepted1E !dinter1E weight_dinter /=.
    have h_mu : mu [1..6] (fun (r0:int) => !1<=r0<=4) = 1%r / 3%r.
      have -> : mu [1..6] (fun (r0:int) => !1<=r0<=4) =
                mu [1..6] (predU (pred1 5) (pred1 6))
        by apply mu_eq_support => r0; rewrite supp_dinter /=; smt().
      have -> : mu [1..6] (predU (pred1 5) (pred1 6)) =
                mu [1..6] (pred1 5) + mu [1..6] (pred1 6)
        by apply mu_disjointL => x /=; smt().
      by rewrite !dinter1E /= /#.
    rewrite h_mu; smt(supp_dexcepted supp_dinter).
  + by rewrite supp_dexcepted /=; smt(supp_dinter).
qed.

equiv D6_Sample: D6.sample ~ D4_6.SampleWi.sample: r{2} = 5 ==> ={res}.
proof.
  (* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  proc; while (={r} /\ (5 <= r{1} <=> (fun (r0 : int) => ! 1 <= r0 <= 4) r{2})); auto; smt().
qed.

lemma D4_D6 (f finv : int -> int) :
    (forall i, 1 <= i <= 4 <=> 1 <= f i <= 4) =>
    (forall i, 1 <= i <= 4 => f (finv i) = i /\ finv (f i) = i) =>
    equiv [D4.sample ~ D6.sample : true ==> res{1} = finv res{2}].
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  move=> hf hfinv.
  have dinter16_ll : is_lossless [1..6] by apply dinter_ll.
  bypr (res{1}) (finv res{2})=> //.
  move=> &1 &2 a.
  have -> : Pr[D4.sample() @ &1 : res = a] = mu1 [1..4] a
    by byphoare=> //; proc; rnd (pred1 a); auto=> />.
  have -> : Pr[D6.sample() @ &2 : finv res = a] =
            Pr[D4_6.SampleWi.sample(tt, 5) @ &2 : finv res = a]
    by byequiv D6_Sample=> //.
  have -> := D4_6.pr_sampleWi &2 tt 5 (fun r => finv r = a) dinter16_ll.
  simplify.
  have -> : mu ([1..6] \ fun (r:int) => !1 <= r <= 4) (fun (r:int) => finv r = a) =
            mu1 ([1..6] \ fun (r:int) => !1 <= r <= 4) (f a)
    by apply mu_eq_support=> r; rewrite supp_dexcepted supp_dinter /=; smt().
  have h_mu : mu [1..6] (fun (r:int) => !1<=r<=4) = 1%r / 3%r.
    have -> : mu [1..6] (fun (r:int) => !1<=r<=4) =
              mu [1..6] (predU (pred1 5) (pred1 6))
      by apply mu_eq_support => r; rewrite supp_dinter /=; smt().
    have -> : mu [1..6] (predU (pred1 5) (pred1 6)) =
              mu [1..6] (pred1 5) + mu [1..6] (pred1 6)
      by apply mu_disjointL => x /=; smt().
    by rewrite !dinter1E /= /#.
  rewrite dexcepted1E !dinter1E weight_dinter h_mu /=; smt().
qed.

lemma prD6 : forall k &m, Pr[D6.sample() @ &m : res = k] =
      if 1 <= k <= 4 then 1%r/4%r else 0%r.
proof.
(* COMPLETE THIS, REMOVE ADMIT ONCE YOU COMPLETE. DO NOT REMOVE THIS COMMENT *)
  move=> k &m.
  have h : Pr[D4.sample() @ &m : res = k] = Pr[D6.sample() @ &m : res = k].
  byequiv (D4_D6 (fun i => i) (fun i => i) _ _)=> //; smt().
  rewrite -h.
  apply prD4.
qed.
