require import AllCore.

op occurrence (x : int) = x = 0.

lemma occurrence_transport (x y : int) :
  x = y => occurrence x = occurrence y.
proof.
  admit.
qed.
