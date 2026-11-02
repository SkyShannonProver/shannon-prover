require import AllCore StdOrder.
import RealOrder.

lemma native_namespace_shadow (x y z : real) : x <= y => y <= z => x <= z.
proof.
