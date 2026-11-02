require import AllCore Int.

module NativeStateCallee = {
  proc bump(x : int) : int = {
    return x + 1;
  }
}.

module NativeStateCaller = {
  proc run(x : int) : int = {
    var y;
    y <@ NativeStateCallee.bump(x);
    return y;
  }
}.

lemma native_state_equiv_statement_goal :
  equiv[NativeStateCaller.run ~ NativeStateCaller.run : ={arg} ==> ={res}].
proof.
