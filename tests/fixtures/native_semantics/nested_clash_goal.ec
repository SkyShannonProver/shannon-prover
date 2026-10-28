require import AllCore.

lemma nested_clash (a b c : bool) :
  a => a /\ b /\ c => true.
proof.
