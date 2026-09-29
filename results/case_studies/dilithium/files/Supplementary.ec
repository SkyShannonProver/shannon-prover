require import AllCore List RealSeries Finite.

require import StdBigop.

import Bigreal BRA StdOrder.RealOrder.

pred image (f : 'a -> 'b) y = exists x, f x = y.

pred injective_in P (f : 'a -> 'b) =
  forall x y, P x => P y => f x = f y => x = y.

lemma map_mkseq (f : 'a -> 'b) (g: int -> 'a) (n : int) :
  0 <= n =>
  map f (mkseq g n) = mkseq (f \o g) n.

proof.

move => ge0_n.

apply (eq_from_nth witness).

rewrite size_map !size_mkseq //.

move => i rg_i.

rewrite size_map size_mkseq in rg_i.

rewrite (nth_map witness); first smt(size_mkseq).

by rewrite !nth_mkseq /#.

qed.

lemma leq_size_to_seq (p q : 'a -> bool) :
  p <= q => is_finite q =>
  size (to_seq p) <= size (to_seq q).

proof.

move => sub_p_q fin_q.

have fin_p : is_finite p by apply (finite_leq _ _ sub_p_q).

apply uniq_leq_size; 1: exact uniq_to_seq.

by move => x; rewrite !mem_to_seq //; exact sub_p_q.

qed.

op locked (x : 'a) = x axiomatized by unlock.

lemma lock (x : 'a) : x = locked x by rewrite unlock.
