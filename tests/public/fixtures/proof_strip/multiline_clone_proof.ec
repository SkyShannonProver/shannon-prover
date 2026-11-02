(* A clone whose proof clause spans several lines, in a minimal environment. *)
require import AllCore List.

theory TT.
  op qHC : int.
  axiom ge0_qHC : 0 <= qHC.
end TT.

abstract theory PlugAndPray.
  type tval.
  type tin.
  type tres.
  op indices : tval list.
  axiom indices_not_nil : indices <> [].
end PlugAndPray.

type guess_trace = int.

clone PlugAndPray as TraceGuess with
  type tval <- int,
  op indices <- iota_ 0 (TT.qHC + 1),
  type tin <- unit,
  type tres <- guess_trace
  proof indices_not_nil by
    (rewrite -List.size_eq0 List.Iota.size_iota; smt(TT.ge0_qHC)).

lemma target : true.
proof.
  trivial.
qed.
