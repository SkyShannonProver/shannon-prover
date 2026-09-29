require import AllCore.

lemma native_pure_tail_local_fact_goal (a b c : int) :
  a = b => a = c => b = c.
proof.
