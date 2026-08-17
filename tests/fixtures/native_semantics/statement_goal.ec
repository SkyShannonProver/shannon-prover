require import AllCore Int.

module NativeStateFixture = {
  var g : int

  proc run(x : int) : int = {
    var y;
    y <- x + 1;
    if (y < 0) {
      y <- -y;
    } else {
      g <- y;
    }
    return y;
  }
}.

lemma native_state_statement_goal :
  hoare[NativeStateFixture.run : true ==> true].
proof.
