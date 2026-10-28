(* The companion's only composition root for feature realizers.  Adding or
   removing a feature's realizer file changes this list and nothing else in
   the companion.  Order is not semantic: every requested realizer runs. *)

let all : Realizer.t list = List.concat [
  Intro_pattern_repair.realizers;
  Operation_binding_repair.realizers;
  Phl_transitivity_boundary_repair.realizers;
  Pure_tail_recovery.realizers;
  Relation_bridge_realization.realizers;
  Tactic_dialect_repair.realizers;
]
