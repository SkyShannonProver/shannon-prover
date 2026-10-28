(* phl_transitivity_boundary_repair: a pRHL transitivity written for the
   other judgment form (function versus statement) than the current goal. *)

open EcLib
open Native_semantic_support

let side_string = function
  | `Left -> "left"
  | `Right -> "right"

let boundary ~tactic = function
  | Realizer.Unsupported_shape _ -> begin
      try
        let tactics = parse_tactics tactic in
        let core = match tactics with
          | [{ EcParsetree.pt_core = core; pt_intros = [] }] -> core
          | _ -> raise (Contract_error
              "PHL transitivity is not one plain tactic")
        in
        let attempted_form, side = match located_desc core with
          | EcParsetree.PPhl (EcParsetree.Ptrans_stmt (kind, _)) -> begin
              match kind with
              | EcParsetree.TKfun _ -> "function", ""
              | EcParsetree.TKstmt (side, _)
              | EcParsetree.TKparsedStmt (side, _, _) ->
                  "statement", side_string side
            end
          | _ -> raise (Contract_error "not a PHL transitivity tactic")
        in
        match phl_goal_form () with
        | None -> None
        | Some current_goal_form when current_goal_form = attempted_form -> None
        | Some current_goal_form ->
            let execution_error =
              try ignore (run_tactics tactics); None with
              | Assert_failure _ -> None
              | exn ->
                  match tactic_rejection_json exn ~invalid_shape:
                      "PHL transitivity form does not match the current goal"
                  with
                  | Some error -> Some error
                  | None -> raise exn
            in
            Option.map (fun error -> {
              Realizer.failure_kind = "phl_transitivity_boundary_mismatch";
              core = Some {
                Realizer.family = "transitivity";
                resource = "";
                argument_kinds = ["phl_" ^ attempted_form];
                side;
                error_message = error_message error;
                application_head = `Null;
              };
              payload = `Assoc [
                "source_operation", `String "transitivity";
                "attempted_form", `String attempted_form;
                "current_goal_form", `String current_goal_form;
                "side", `String side;
              ];
            }) execution_error
      with
      | EcParsetree.ParseError _
      | Contract_error _ -> None
    end
  | _ -> None

let realizers = [
  { Realizer.kind = "phl_transitivity_boundary_repair.boundary";
    realize = boundary };
]
