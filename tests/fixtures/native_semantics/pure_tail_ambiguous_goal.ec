require import AllCore FMap.

lemma native_pure_tail_ambiguous_goal
  (m : (int, int) fmap) (x v : int) (z1 z2 : int option) :
  m.[x <- v].[x] = z1 => m.[x <- v].[x] = z2 => z1 = z2.
proof.
