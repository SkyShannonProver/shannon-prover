require import AllCore.

theory UnitArgument.
  type t.

  module type Callee = {
    proc run(_ : t) : unit
  }.

  module Caller (M : Callee) = {
    proc f(x : t) : unit = {
      M.run(x);
    }
  }.
end UnitArgument.

clone import UnitArgument as UA with type t <- unit.

module UnitCallee : UA.Callee = {
  proc run() : unit = { }
}.

lemma native_state_unit_argument_goal :
  hoare[UA.Caller(UnitCallee).f : true ==> true].
proof.
