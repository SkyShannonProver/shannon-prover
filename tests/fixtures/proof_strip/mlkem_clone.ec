(* ML-KEM's failing clone shape, with a minimal independent environment. *)
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

type mlkem_corr_trace = int.

clone PlugAndPray as MlkemCorrGuess with
  type tval <- int,
  op indices <- iota_ 0 (TT.qHC + 1),
  type tin <- unit,
  type tres <- mlkem_corr_trace
  proof indices_not_nil by
    (rewrite -List.size_eq0 List.Iota.size_iota; smt(TT.ge0_qHC)).

lemma target : true.
proof.
  trivial.
qed.
