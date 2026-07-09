(* Fixtures for tests/test_infer_remaining_goals.py — each lemma reaches
   a known branch point after a short tactic prefix, so we can validate
   what EC actually classifies each subgoal as. *)

require import AllCore Int Real Distr DBool.

module M = {
  var x : int
  proc f() : int = { x <- 1; x <- x + 1; return x; }
  proc g(y : int) : int = { if (y < 0) { y <- -y; } else { y <- y + 1; } return y; }
  proc loop() : int = { var i; i <- 0; while (i < 10) { i <- i + 1; } return i; }
}.

(* seq K : produces 2 hoare subgoals *)
lemma test_seq : hoare[M.f : true ==> res = 2].
proof.
  proc.
admit.
qed.

(* if tactic produces 2 hoare subgoals *)
lemma test_if : hoare[M.g : true ==> true].
proof.
  proc.
admit.
qed.

(* while tactic produces 3 subgoals (body, term, inv→post) *)
lemma test_while : hoare[M.loop : true ==> res = 10].
proof.
  proc.
admit.
qed.

(* conseq splits into 2 subgoals (ambient sidecond + main with new post) *)
lemma test_conseq : hoare[M.f : true ==> res = 2].
proof.
admit.
qed.

(* Real call scenario: procedure A calls procedure B. *)
module Oracle = {
  var y : int
  proc update() : int = { y <- y + 1; return y; }
}.

module Caller = {
  proc run() : int = { var r; r <@ Oracle.update(); return r; }
}.

lemma test_call : equiv[Caller.run ~ Caller.run : ={Oracle.y} ==> ={res, Oracle.y}].
proof.
admit.
qed.
