require import AllCore Int.

module SmtFailureLoop = {
  proc run(n : int) : int = {
    var i : int;
    i <- 0;
    while (i < n) {
      i <- i + 1;
    }
    return i;
  }
}.

lemma native_smt_failure_program :
  phoare [SmtFailureLoop.run : 0 <= n ==> 0 <= res] = 1%r.
proof.
