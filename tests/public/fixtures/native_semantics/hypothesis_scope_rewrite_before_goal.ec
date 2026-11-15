require import AllCore List.

lemma native_hypothesis_scope_rewrite_before_goal (b c : bool) (l : int list) :
  b || c => size l = 0 => l = [].
proof.
