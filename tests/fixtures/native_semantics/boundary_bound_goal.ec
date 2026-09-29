require import AllCore.

module type NativeBoundOracle = {
  proc f() : unit
}.

module NativeBoundO1 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO2 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO3 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO4 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO5 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO6 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO7 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO8 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO9 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO10 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO11 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO12 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO13 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO14 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO15 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO16 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO17 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO18 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO19 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO20 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO21 : NativeBoundOracle = {
  proc f() = {}
}.

module NativeBoundO22 : NativeBoundOracle = {
  proc f() = {}
}.

axiom native_bound_depths (O <: NativeBoundOracle) :
  islossless NativeBoundO1.f => islossless NativeBoundO2.f => islossless O.f.

lemma native_bound_goal : islossless NativeBoundO7.f.
proof.
