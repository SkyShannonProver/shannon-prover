module NativeEagerGuard = {
  proc left() = {
    var x : int;
    x <- 0;
    while (true) {}
  }

  proc right() = {
    var x : int;
    while (false) {}
    x <- 0;
  }
}.

lemma native_eager_while_guard_goal :
  equiv[NativeEagerGuard.left ~ NativeEagerGuard.right : true ==> true].
proof.
