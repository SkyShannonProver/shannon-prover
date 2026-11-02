require import AllCore.

module type NativeLosslessOracle = {
  proc f() : unit
}.

module type NativeLosslessAdv (O : NativeLosslessOracle) = {
  proc run() : bool
}.

section.

declare module A <: NativeLosslessAdv.

declare axiom native_A_ll (O <: NativeLosslessOracle {-A}) :
  islossless O.f => islossless A(O).run.

lemma native_lossless_premise (O <: NativeLosslessOracle {-A}) :
  islossless O.f => islossless A(O).run.
proof.
