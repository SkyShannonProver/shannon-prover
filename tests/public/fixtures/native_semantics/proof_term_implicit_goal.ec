require import AllCore Int.
pragma +implicits.

lemma native_implicit_descriptor (x y : int) : x = y => x = x.
proof.
move=> H.
trivial.
qed.

lemma native_implicit_goal : 0 = 1 => true.
proof.
