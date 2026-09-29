require import AllCore.

module type NativeViewOracle = {
  proc f() : unit
}.

module NativeViewO1 : NativeViewOracle = {
  proc f() = {}
}.

op native_view_f : int -> int.
op native_view_p : int -> bool.
op native_view_q : int -> bool.

axiom native_view_inj (O <: NativeViewOracle) : injective native_view_f.

axiom native_view_iff (O <: NativeViewOracle) (x : int) :
  native_view_p x <=> native_view_q x.

lemma native_view_iff_goal : native_view_q 3.
proof.
