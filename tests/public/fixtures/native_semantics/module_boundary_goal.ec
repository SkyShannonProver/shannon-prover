require import AllCore.

module type NativeBoundaryOracle = {
  proc f() : unit
}.

module NativeBoundaryO1 : NativeBoundaryOracle = {
  proc f() = {}
}.

module NativeBoundaryO2 : NativeBoundaryOracle = {
  proc f() = {}
}.

axiom native_boundary (A <: NativeBoundaryOracle) (O <: NativeBoundaryOracle) :
  islossless A.f => islossless O.f.

lemma native_boundary_goal :
  forall (O <: NativeBoundaryOracle),
    islossless NativeBoundaryO1.f => islossless O.f.
proof.
