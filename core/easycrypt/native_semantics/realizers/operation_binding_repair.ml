(* operation_binding_repair: a [call] whose first module argument omits the
   [(<: M)] grammar, so EasyCrypt could not parse it.  The realizer inserts
   only that punctuation to formulate one native query. *)

open EcLib
open Native_semantic_support

let bounded_application_text value =
  let length = String.length value in
  length > 0 && length <= 4096
  && not (String.contains value ';')
  && not (String.contains value '\n')
  && not (String.contains value '\r')
  && not (String.contains value '"')
  && not (String.contains value '|')
  && not (contains_substring value "(*")
  && not (contains_substring value "*)")

let outer_parenthesized_body value =
  let length = String.length value in
  if length < 2 || value.[0] <> '(' || value.[length - 1] <> ')' then None
  else
    let rec scan index depth =
      if index >= length then None else
      let depth' = match value.[index] with
        | '(' -> depth + 1
        | ')' -> depth - 1
        | _ -> depth
      in
      if depth' < 0 then None
      else if depth' = 0 then
        if index = length - 1 then
          Some (String.sub value 1 (length - 2) |> String.trim)
        else None
      else scan (index + 1) depth'
    in scan 0 0

let first_space value =
  let rec scan index =
    if index >= String.length value then None
    else if value.[index] = ' ' || value.[index] = '\t'
    then Some index else scan (index + 1)
  in scan 0

let first_application_argument value =
  let value = String.trim value in
  let length = String.length value in
  if length = 0 then None
  else if value.[0] = '(' then
    let rec scan index depth =
      if index >= length then None else
      let depth' = match value.[index] with
        | '(' -> depth + 1
        | ')' -> depth - 1
        | _ -> depth
      in
      if depth' < 0 then None
      else if depth' = 0 then
        let argument = String.sub value 1 (index - 1) |> String.trim in
        let suffix = String.sub value (index + 1)
          (length - index - 1) |> String.trim in
        Some (argument, suffix, true)
      else scan (index + 1) depth'
    in scan 0 0
  else
    let rec scan index depth =
      if index >= length then
        Some (String.trim value, "", false)
      else match value.[index] with
      | '(' -> scan (index + 1) (depth + 1)
      | ')' when depth > 0 -> scan (index + 1) (depth - 1)
      | ')' -> None
      | (' ' | '\t') when depth = 0 ->
          let argument = String.sub value 0 index |> String.trim in
          let suffix = String.sub value index (length - index)
            |> String.trim in
          Some (argument, suffix, false)
      | _ -> scan (index + 1) depth
    in scan 0 0

let ambiguous_unparenthesized_suffix suffix parenthesized =
  not parenthesized && String.length suffix > 0
  && (suffix.[0] = '(' || suffix.[0] = '.')

let call_module_syntax_candidate tactic_text =
  let prefix = "call " in
  let length = String.length tactic_text in
  if not (bounded_application_text tactic_text)
     || length <= String.length prefix + 2
     || not (String.starts_with ~prefix tactic_text)
     || tactic_text.[length - 1] <> '.' then None
  else
    let term = String.sub tactic_text (String.length prefix)
      (length - String.length prefix - 1) |> String.trim in
    match outer_parenthesized_body term with
    | None -> None
    | Some application -> begin match first_space application with
        | None -> None
        | Some separator ->
            let resource = String.sub application 0 separator |> String.trim in
            let arguments = String.sub application (separator + 1)
              (String.length application - separator - 1) |> String.trim in
            begin match first_application_argument arguments with
            | None -> None
            | Some (module_term, suffix, parenthesized) ->
                if resource = "" || module_term = ""
                   || contains_substring module_term "<:"
                   || ambiguous_unparenthesized_suffix suffix parenthesized
                then None else
                let candidate_application = resource ^ " (<: " ^ module_term
                  ^ ")" ^ (if suffix = "" then "" else " " ^ suffix) in
                Some (resource, module_term, candidate_application,
                  "call (" ^ candidate_application ^ ").")
            end
        end

let first_application_slot_is_module = function
  | `Assoc fields -> begin match List.assoc_opt "slots" fields with
      | Some (`List (`Assoc slot :: _)) -> begin
          match List.assoc_opt "kind" slot with
          | Some (`String "module") -> true
          | _ -> false
        end
      | _ -> false
    end
  | _ -> false

let module_argument_syntax ~tactic = function
  | Realizer.Parse_error parse_message -> begin
      match call_module_syntax_candidate tactic with
      | None -> None
      | Some (resource, module_term, candidate_application, candidate_tactic) ->
          begin try
            let attempted = parse_attempted_tactic candidate_tactic in
            match attempted.at_family, attempted.at_resource,
                attempted.at_argument_kinds, application_head_result attempted with
            | "call", selected, ("module" :: _ as argument_kinds), Some head
                when selected = resource && first_application_slot_is_module head ->
                Some {
                  Realizer.failure_kind = "application_module_argument_syntax";
                  core = Some {
                    Realizer.family = "call";
                    resource;
                    argument_kinds = [];
                    side = "";
                    error_message = parse_message;
                    application_head = head;
                  };
                  payload = `Assoc [
                    "source_operation", `String "call";
                    "selected_resource", `String resource;
                    "module_argument_position", `Int 1;
                    "module_term_text", `String module_term;
                    "candidate_application_term", `String candidate_application;
                    "candidate_tactic", `String candidate_tactic;
                    "candidate_argument_kinds", `List (List.map
                      (fun value -> `String value) argument_kinds);
                    "resolved_candidate_count", `Int 1;
                  ];
                }
            | _ -> None
          with
          | EcParsetree.ParseError _
          | EcCoreGoal.TcError _
          | EcProofTerm.ProofTermError _
          | EcTyping.TyError _
          | EcEnv.LookupFailure _
          | Contract_error _
          | Assert_failure _ -> None
          end
    end
  | _ -> None

let realizers = [
  { Realizer.kind = "operation_binding_repair.module_argument_syntax";
    realize = module_argument_syntax };
]
