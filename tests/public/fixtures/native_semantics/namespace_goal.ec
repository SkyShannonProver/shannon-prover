require import AllCore.
require StdOrder.

lemma native_namespace_helper : true.
proof. by []. qed.

lemma native_namespace_goal (x y z : real) : x <= y => y <= z => x <= z.
proof.
