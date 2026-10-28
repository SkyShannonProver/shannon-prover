(* tactic_dialect_repair: [eager while] written with an explicit statement
   contract instead of one invariant, or with an invariant whose two while
   guards are not syntactically equal. *)

open EcLib
open Native_semantic_support

let bounded_eager_formula value =
  let length = String.length value in
  length > 0 && length <= 4096
  && not (String.contains value ';')
  && not (String.contains value '\n')
  && not (String.contains value '\r')
  && not (String.contains value '"')

let eager_while_contract_formulas tactic_text =
  let prefix = "eager while (" in
  let suffix = ")." in
  let prefix_length = String.length prefix in
  let suffix_length = String.length suffix in
  let length = String.length tactic_text in
  if length <= prefix_length + suffix_length
     || not (String.starts_with ~prefix tactic_text)
     || not (String.ends_with ~suffix tactic_text) then None
  else
    let body = String.sub tactic_text prefix_length
      (length - prefix_length - suffix_length) in
    match top_level_positions body " : " with
    | None | Some [] -> None
    | Some positions ->
        let colon = List.hd (List.rev positions) in
        let contract_start = colon + String.length " : " in
        let contract = String.sub body contract_start
          (String.length body - contract_start) in
        begin match top_level_positions contract " ==> " with
        | Some [arrow] ->
            let left = String.sub contract 0 arrow |> String.trim in
            let right_start = arrow + String.length " ==> " in
            let right = String.sub contract right_start
              (String.length contract - right_start) |> String.trim in
            if bounded_eager_formula left && bounded_eager_formula right
            then Some (left, right) else None
        | _ -> None
        end

let unique_strings values =
  List.fold_left (fun kept value ->
    if List.mem value kept then kept else kept @ [value]) [] values

let eager_while_claim attempted_shape failure_kind error_message candidates =
  {
    Realizer.failure_kind;
    core = Some {
      Realizer.family = "eager";
      resource = "";
      argument_kinds = [if attempted_shape = "invariant"
        then "formula" else "eager_while_contract"];
      side = "";
      error_message;
      application_head = `Null;
    };
    payload = `Assoc [
      "source_operation", `String "eager";
      "eager_subform", `String "while";
      "attempted_shape", `String attempted_shape;
      "candidates", `List (List.map (fun invariant -> `Assoc [
        "invariant_text", `String invariant;
        "candidate_tactic", `String ("eager while (" ^ invariant ^ ").");
      ]) candidates);
    ];
  }

let explicit_contract tactic parse_message =
  match phl_goal_form (), eager_while_contract_formulas tactic with
  | Some "statement", Some (precondition, postcondition) ->
      let candidates = unique_strings [precondition; postcondition]
        |> List.filter (fun invariant -> native_preflight_candidate
          ("eager while (" ^ invariant ^ ").")) in
      if candidates = [] && not (native_preflight_candidate
          "eager while (true).") then None
      else Some (eager_while_claim "explicit_statement_contract"
        "eager_while_dialect_mismatch" parse_message candidates)
  | _ -> None

let guard_mismatch tactic =
  try
    let tactics = parse_tactics tactic in
    let core = match tactics with
      | [{ EcParsetree.pt_core = core; pt_intros = [] }] -> core
      | _ -> raise (Contract_error "eager while is not one plain tactic")
    in
    match located_desc core, phl_goal_form () with
    | EcParsetree.PPhl (EcParsetree.Peager_while _), Some "statement" ->
        let execution_error =
          try ignore (run_tactics tactics); None with
          | Assert_failure _ -> None
          | exn ->
              match tactic_rejection_json exn ~invalid_shape:
                  "eager while is not valid at this boundary" with
              | Some error -> Some error
              | None -> raise exn
        in
        begin match execution_error with
        | Some error when contains_substring (error_message error)
            "both while guards must be syntactically equal" ->
            Some (eager_while_claim "invariant" "eager_while_guard_mismatch"
              (error_message error) [])
        | _ -> None
        end
    | _ -> None
  with
  | EcParsetree.ParseError _
  | Contract_error _ -> None

let eager_while ~tactic = function
  | Realizer.Parse_error message -> explicit_contract tactic message
  | Realizer.Unsupported_shape _ -> guard_mismatch tactic
  | Realizer.Parsed _ -> None

let realizers = [
  { Realizer.kind = "tactic_dialect_repair.eager_while";
    realize = eager_while };
]
