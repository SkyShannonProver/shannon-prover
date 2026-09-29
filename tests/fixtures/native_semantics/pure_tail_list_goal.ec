require import AllCore List.

lemma native_pure_tail_list_goal (xs : int list) (n : int) :
  size (xs ++ []) = n => n = size xs.
proof.
