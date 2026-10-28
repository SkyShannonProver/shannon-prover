(* pure_tail_recovery: the agent's exact left-to-right rewrite fails at the
   conclusion and succeeds at exactly one named hypothesis. *)

open EcLib
open Native_semantic_support

let rewrite_target ~tactic:_ = function
  | Realizer.Parsed attempted
    when attempted.at_family = "rewrite" && attempted.at_resource <> "" ->
      let local_hypotheses =
        (EcEnv.LDecl.tohyps
          (EcCoreGoal.FApi.tc1_hyps (current_tcenv1 ()))).EcBaseLogic.h_local in
      let candidates = List.filter_map (fun (identifier, local_kind) ->
        match local_kind with
        | EcBaseLogic.LD_hyp _ ->
            let target = EcIdent.name identifier in
            let tactic = "rewrite " ^ attempted.at_resource ^ " in "
              ^ target ^ "." in
            (* A local equality can often rewrite itself.  That is an
               executable but circular target repair, so it is not part of
               the candidate population. *)
            if target <> attempted.at_resource
              && native_preflight_candidate tactic
            then Some (target, tactic)
            else None
        | _ -> None) local_hypotheses in
      begin match candidates with
      | [(target, tactic)] -> Some {
          Realizer.failure_kind = "rewrite_target_mismatch";
          core = None;
          payload = `Assoc [
            "source_operation", `String "rewrite";
            "selected_resource", `String attempted.at_resource;
            "target_kind", `String "hypothesis";
            "target_name", `String target;
            "candidate_tactic", `String tactic;
            "accepted_target_count", `Int 1;
          ];
        }
      | _ -> None
      end
  | _ -> None

let realizers = [
  { Realizer.kind = "pure_tail_recovery.rewrite_target";
    realize = rewrite_target };
]
