require import AllCore Int.

op eps : int = 0.
op holds (x : int) : bool.
axiom holds_all : forall (x : int), holds x.

lemma native_smt_failure_goal (x y : int) :
  0 <= x => x + eps = x /\ holds x /\ (0 <= x + 1) /\ holds y.
proof.
