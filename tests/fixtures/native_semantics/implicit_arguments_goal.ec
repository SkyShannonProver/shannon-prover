require import AllCore.

pragma +implicits.

axiom native_implicit_le (x : int) : 0 <= x => x <= x.

lemma native_implicit_goal (y : int) : 0 <= y => y <= y.
proof.
