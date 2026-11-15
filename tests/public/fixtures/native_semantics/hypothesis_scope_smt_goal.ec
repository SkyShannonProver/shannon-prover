require import AllCore.

op f : int -> bool.
axiom f_all : forall (y : int), f y.

lemma native_hypothesis_scope_smt_goal (g : int -> bool) (x : int) :
  (forall y, g y) => g x.
proof.
