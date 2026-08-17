require import AllCore.

module type NativeDescriptorOracle = {
  proc f() : unit
}.

module NativeDescriptorImpl : NativeDescriptorOracle = {
  proc f() : unit = {
  }
}.

module NativeDescriptorNest (O : NativeDescriptorOracle) = {
  module O = O
}.

lemma native_descriptor_certificate (O <: NativeDescriptorOracle) :
  islossless O.f => islossless O.f.
proof.
move=> H.
exact H.
qed.

lemma native_formula_head (b : bool) : b => b.
proof.
move=> H.
exact H.
qed.

lemma native_descriptor_goal : true.
proof.
