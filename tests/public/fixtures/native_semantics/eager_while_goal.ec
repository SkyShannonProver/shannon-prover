module NativeEagerWhile = {
  proc left() = {
    var x : int;
    x <- 0;
    while (true) {}
    while (false) {}
  }

  proc right() = {
    var x : int;
    while (false) {}
    x <- 0;
    while (true) {}
  }
}.

lemma native_eager_while_goal :
  equiv[NativeEagerWhile.left ~ NativeEagerWhile.right : true ==> true].
proof.
