(* intro_pattern_repair: a [move=>] whose one nested case tree of named
   binders does not fit the goal, while the flat [#] destructuring of the
   same binders does. *)

open EcLib
open Native_semantic_support

let rec flatten_named_intro_pattern pattern =
  let rec fold remaining names has_case = match remaining with
    | [] -> Some (names, has_case)
    | item :: tail -> begin
        match located_desc item with
        | EcParsetree.IPCore (`Named name) ->
            fold tail (names @ [name]) has_case
        | EcParsetree.IPCase (`One, [branch]) -> begin
            match flatten_named_intro_pattern branch with
            | Some (nested_names, _) ->
                fold tail (names @ nested_names) true
            | None -> None
            end
        | _ -> None
        end
  in fold pattern [] false

let selected_nested_intro_pattern patterns =
  let rec scan remaining selected = match remaining with
    | [] -> selected
    | item :: tail -> begin
        match located_desc item with
        | EcParsetree.IPCore (`Named _) -> scan tail selected
        | EcParsetree.IPCase (`One, [branch]) -> begin
            match selected, flatten_named_intro_pattern branch with
            | None, Some (names, true) -> scan tail (Some names)
            | _ -> None
            end
        | _ -> None
        end
  in
  match scan patterns None with
  | Some names when List.length names >= 2 && List.length names <= 32
      && List.length names =
        List.length (List.sort_uniq String.compare names) -> Some names
  | _ -> None

let single_outer_bracket_span_after_intro text =
  match top_level_positions text "=>" with
  | Some [arrow] ->
      let rec scan index depth opened spans =
        if index >= String.length text then
          if depth = 0 && opened = None then Some (List.rev spans) else None
        else match text.[index] with
        | '[' when depth = 0 -> scan (index + 1) 1 (Some index) spans
        | '[' -> scan (index + 1) (depth + 1) opened spans
        | ']' when depth = 1 -> begin match opened with
            | Some start -> scan (index + 1) 0 None ((start, index) :: spans)
            | None -> None
            end
        | ']' when depth > 1 -> scan (index + 1) (depth - 1) opened spans
        | ']' -> None
        | _ -> scan (index + 1) depth opened spans
      in
      begin match scan (arrow + 2) 0 None [] with
      | Some [span] -> Some span
      | _ -> None
      end
  | _ -> None

let replace_text_span text (start_index, end_index) replacement =
  String.sub text 0 start_index ^ replacement ^
  String.sub text (end_index + 1)
    (String.length text - end_index - 1)

let nested_case ~tactic = function
  | Realizer.Unsupported_shape _ -> begin
      try
        let tactics = parse_tactics tactic in
        let surface_operation, patterns = match tactics with
          | [{ EcParsetree.pt_core = core;
               pt_intros = [`Ip patterns]; _ }] -> begin
              match located_desc core with
              | EcParsetree.Plogic (EcParsetree.Pmove _) -> "move", patterns
              | _ -> raise (Contract_error
                  "intro-pattern repair requires move")
              end
          | _ -> raise (Contract_error
              "intro-pattern repair requires one tactic and one intro group")
        in
        let binder_names = match selected_nested_intro_pattern patterns with
          | Some names -> names
          | None -> raise (Contract_error
              "intro-pattern repair requires one named nested case tree")
        in
        let span = match single_outer_bracket_span_after_intro tactic with
          | Some span -> span
          | None -> raise (Contract_error
              "intro-pattern repair could not isolate one selected case tree")
        in
        let replacement = "[# " ^ String.concat " " binder_names ^ "]" in
        let candidate_tactic = replace_text_span tactic span replacement in
        let execution_error =
          try ignore (run_tactics tactics); None with
          | exn ->
              match tactic_rejection_json exn ~invalid_shape:
                  "the selected intro pattern does not fit the current goal"
              with
              | Some error -> Some error
              | None -> raise exn
        in
        match execution_error with
        | Some error when native_preflight_candidate candidate_tactic ->
            Some {
              Realizer.failure_kind = "intro_pattern_structure_mismatch";
              core = Some {
                Realizer.family = "intro_pattern";
                resource = "";
                argument_kinds = ["ordered_named_binders"];
                side = "";
                error_message = error_message error;
                application_head = `Null;
              };
              payload = `Assoc [
                "source_operation", `String "intro_pattern";
                "surface_operation", `String surface_operation;
                "attempted_pattern_kind", `String "nested_case";
                "binder_names", `List
                  (List.map (fun name -> `String name) binder_names);
                "candidate_tactic", `String candidate_tactic;
                "selected_pattern_count", `Int 1;
              ];
            }
        | _ -> None
      with
      | EcParsetree.ParseError _
      | EcCoreGoal.TcError _
      | EcTyping.TyError _
      | EcEnv.LookupFailure _
      | Contract_error _
      | Assert_failure _ -> None
    end
  | _ -> None

let realizers = [
  { Realizer.kind = "intro_pattern_repair.nested_case";
    realize = nested_case };
]
