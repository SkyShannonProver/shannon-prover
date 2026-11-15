require import AllCore List.

lemma native_hypothesis_scope_rewrite_goal (b c : bool) (l : int list) :
  (if b || c then [] else l) = l => b || c => l = [].
proof.
