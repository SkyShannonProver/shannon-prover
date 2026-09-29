require import AllCore FMap.

lemma native_pure_tail_map_goal
  (m : (int, int) fmap) (x v : int) (z : int option) :
  m.[x <- v].[x] = z => z = Some v.
proof.
