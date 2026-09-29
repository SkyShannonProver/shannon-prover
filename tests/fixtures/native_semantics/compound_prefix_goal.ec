require import AllCore Int.

op eps : int = 0.
op holds (x : int) : bool.
axiom holds_all : forall (x : int), holds x.

lemma native_compound_prefix_goal :
  forall (x : int), true => x + eps = x /\ holds x.
proof.
