require import AllCore.

module type NativeKindOracle = {
  proc f() : unit
}.

module NativeKindO1 : NativeKindOracle = {
  proc f() = {}
}.

axiom native_kind_mem (O <: NativeKindOracle) &m : true.

axiom native_kind_nest : true => true.

op native_unfold_q : bool = forall (y : int), true.

axiom native_unfold_lq (x : int) : native_unfold_q.

lemma native_kind_goal : true.
proof.
