require import AllCore.

module type NativeBindingOracle = {
  proc f() : unit
}.

module NativeBindingOne : NativeBindingOracle = {
  proc f() : unit = {
  }
}.

module NativeBindingTwo : NativeBindingOracle = {
  proc f() : unit = {
  }
}.

module NativeBindingThree = NativeBindingOne.
module NativeBindingFour = NativeBindingOne.
module NativeBindingFive = NativeBindingOne.
module NativeBindingSix = NativeBindingOne.
module NativeBindingSeven = NativeBindingOne.
module NativeBindingEight = NativeBindingOne.
module NativeBindingNine = NativeBindingOne.

module NativeBindingWrong = {
  var x : int
}.

lemma native_binding_true (O <: NativeBindingOracle) : true.
proof.
trivial.
qed.

lemma native_binding_pair
    (O1 <: NativeBindingOracle) (O2 <: NativeBindingOracle) : true.
proof.
trivial.
qed.

axiom native_binding_false (O <: NativeBindingOracle) : false.

lemma native_binding_goal : true.
proof.
