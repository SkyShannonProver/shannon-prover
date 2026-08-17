require import AllCore FMap.

lemma pure_tail_rewrite_micro
  (m : (int, int) fmap) (x v : int) (z : int option) :
  m.[x <- v].[x] = z => z = Some v.
proof.
  move=> Hupdate.
  rewrite get_setE in Hupdate.
  smt().
qed.
