require import AllCore Int.

op eps : int = 0.
op holds (x : int) : bool.
axiom holds_all : forall (x : int), holds x.

lemma compound_prefix_continuation :
  forall (x : int), true => x + eps = x /\ holds x.
proof.
  move=> x _.
  rewrite /eps.
  split; first smt().
  exact (holds_all x).
qed.
