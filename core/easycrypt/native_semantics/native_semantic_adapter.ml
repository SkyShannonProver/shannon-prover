(* Narrow read-only native semantic-query probe.

   The process reconstructs an EasyCrypt proof state from a manager-owned
   extracted context and committed tactic prefix, then asks EcProofTerm to
   elaborate one bounded ordered batch of exact application terms after one
   replay.  The caller must bind paths, hashes,
   StateRef, no-mutation checks, artifact authority, and runtime/library build
   identity.  This executable owns none of those harness policies.

   An attempt diagnosis describes the rejected tactic feature-neutrally and
   asks the requested feature realizers (see [Realizer]) whether one of them
   realizes it; that path names no feature.  The query kinds that serve a
   single feature (selected application binding sets, namespace spellings,
   tactic-prefix diagnosis) are still decoded here. *)

open EcLib
open EcAst
open EcCoreGoal
open Yojson.Safe.Util
open Native_semantic_support

let parse_exact_term operation application_term =
  let tactic = operation ^ " (" ^ application_term ^ ")." in
  let globals = parse_sentences tactic in
  match globals with
  | [{ EcParsetree.gl_action = action; _ }] -> begin
      match located_desc action with
      | EcParsetree.Gtactics
          (`Actual (_, [{ EcParsetree.pt_core = core; _ }])) ->
          begin match located_desc core with
          | EcParsetree.Plogic logical -> begin
              match logical with
              | EcParsetree.Papply (`Apply ([term], kind), None)
                when (operation = "apply" && kind = `Apply)
                  || (operation = "exact" && kind = `Exact) ->
                  Logical term
              | _ -> raise (Contract_error "unsupported logical tactic shape")
            end
          | EcParsetree.PPhl phl -> begin
              match phl with
              | EcParsetree.Pcall (None, term) when operation = "call" ->
                  Call term
              | EcParsetree.Pconseq ([], (Some term, None, None))
                  when operation = "conseq" ->
                  Logical (logical_term_of_conseq term)
              | _ -> raise (Contract_error "unsupported call tactic shape")
            end
          | _ -> raise (Contract_error "unsupported tactic core")
          end
      | _ -> raise (Contract_error "request did not parse as one tactic")
    end
  | _ -> raise (Contract_error "request did not parse as one global action")

let argument_value_json ppe = function
  | PAFormula formula -> `Assoc [
      "kind", `String "formula";
      "hole", `Bool false;
      "formula", shallow_formula_json ppe formula;
    ]
  | PAMemory memory -> `Assoc [
      "kind", `String "memory";
      "hole", `Bool false;
      "identity", `String (EcIdent.name memory);
    ]
  | PAModule (path, _) -> `Assoc [
      "kind", `String "module";
      "hole", `Bool false;
      "identity", `String (EcPath.m_tostring path);
    ]
  | PASub None -> `Assoc [
      "kind", `String "proof";
      "hole", `Bool true;
    ]
  | PASub (Some proof) -> begin
      match proof_hole_formula proof with
      | Some formula -> `Assoc [
          "kind", `String "proof";
          "hole", `Bool true;
          "formula", shallow_formula_json ppe formula;
        ]
      | None -> `Assoc [
          "kind", `String "proof";
          "hole", `Bool false;
          "head", head_json ppe (resolved_head proof);
        ]
    end

let replay_head tc = function
  | PTGlobal (path, types) ->
      EcProofTerm.pt_of_global
        (EcCoreGoal.FApi.tc1_penv tc)
        (EcCoreGoal.FApi.tc1_hyps tc)
        path types
  | PTLocal identifier ->
      EcProofTerm.pt_of_hyp
        (EcCoreGoal.FApi.tc1_penv tc)
        (EcCoreGoal.FApi.tc1_hyps tc)
        identifier
  | _ -> raise (Contract_error "descriptor requires a global or local head")

let replay_value = function
  | PAFormula formula -> EcProofTerm.PVAFormula formula
  | PAMemory memory -> EcProofTerm.PVAMemory memory
  | PAModule module_value -> EcProofTerm.PVAModule module_value
  | PASub _ -> raise (Contract_error "proof arguments use implication replay")

let describe_arguments tc ppe head arguments =
  let rec loop index (replay : EcProofTerm.pt_ev)
      arguments descriptors residuals =
    match arguments with
    | [] -> (List.rev descriptors, List.rev residuals, replay.ptev_ax)
    | argument :: tail -> begin
        match EcProofTyping.destruct_product replay.ptev_env.pte_hy replay.ptev_ax with
        | None -> raise (Contract_error "elaborated argument exceeds head product")
        | Some product ->
            let expected = expected_argument_json ppe product in
            let descriptor = `Assoc [
              "position", `Int index;
              "actual", argument_value_json ppe argument;
              "expected", expected;
            ] in
            let residuals = match product with
              | `Imp (premise, _) when is_proof_hole argument ->
                  (`Assoc [
                    "argument_position", `Int index;
                    "formula", shallow_formula_json ppe premise;
                  ]) :: residuals
              | _ -> residuals
            in
            let replay = match product, argument with
              | `Imp (_, conclusion), PASub _ ->
                  { replay with ptev_ax = conclusion }
              | `Forall _, (PAFormula _ | PAMemory _ | PAModule _) ->
                  EcProofTerm.apply_pterm_to_arg_r replay (replay_value argument)
              | `Imp _, _ ->
                  raise (Contract_error "native proof argument kind drifted")
              | `Forall _, PASub _ ->
                  raise (Contract_error "native forall argument kind drifted")
            in
            loop (index + 1) replay tail (descriptor :: descriptors) residuals
      end
  in
  loop 1 (replay_head tc head) arguments [] []

let descriptor_json tc term proof result_formula =
  let environment = EcScope.env (EcCommands.current ()) in
  let ppe = EcPrinting.PPEnv.ofenv environment in
  let head = resolved_head proof in
  let arguments = EcCoreGoal.get_pt_top_args proof in
  let descriptors, residuals, _ =
    describe_arguments tc ppe head arguments
  in
  let input_arguments = List.mapi
    (fun index argument -> input_argument_json (index + 1) argument)
    term.EcParsetree.fp_args
  in
  let explicit_hole_count = List.fold_left
    (fun count argument -> match argument.EcLocation.pl_desc with
      | EcParsetree.EA_none -> count + 1
      | _ -> count)
    0 term.EcParsetree.fp_args
  in
  let source_count = List.length term.EcParsetree.fp_args in
  let elaborated_count = List.length arguments in
  if elaborated_count < source_count then
    raise (Contract_error "native elaboration lost explicit arguments");
  let result_convertible_to_current_goal =
    EcReduction.is_conv
      ~ri:EcReduction.full_compat
      (EcCoreGoal.FApi.tc1_hyps tc)
      result_formula
      (EcCoreGoal.FApi.tc1_goal tc)
  in
  `Assoc [
    "resolved_head", head_json ppe head;
    "input_mode", `String (match term.EcParsetree.fp_mode with
      | `Explicit -> "explicit" | `Implicit -> "implicit");
    "input_arguments", `List input_arguments;
    "explicit_hole_count", `Int explicit_hole_count;
    "implicit_argument_count", `Int (elaborated_count - source_count);
    "arguments", `List descriptors;
    "can_concretize", `Bool true;
    "residual_proof_premises", `List residuals;
    "result", shallow_formula_json ppe result_formula;
    "result_convertible_to_current_goal",
      `Bool result_convertible_to_current_goal;
  ]

let elaborate term =
  let tcenv = current_tcenv1 () in
  let finish parsed (elaborated : EcProofTerm.pt_ev) =
    if not (EcProofTerm.can_concretize elaborated.ptev_env) then
      EcCoreGoal.tc_error elaborated.ptev_env.pte_pe
        "cannot infer all placeholders";
    let proof, formula = EcProofTerm.concretize elaborated in
    let environment = EcScope.env (EcCommands.current ()) in
    let formula_text = Format.asprintf "%a"
      (EcPrinting.pp_form (EcPrinting.PPEnv.ofenv environment)) formula in
    (formula_text, descriptor_json tcenv parsed proof formula)
  in
  match term with
    | Logical term ->
        let implicits = EcScope.Options.get_implicits (EcCommands.current ()) in
        finish term
          (EcProofTerm.tc1_process_full_pterm ~implicits tcenv term)
    | Call term ->
        finish term (EcProofTerm.tc1_process_full_pterm_cut
          ~prcut:(fun _ ->
            raise (Contract_error "inline call specifications are unsupported"))
          tcenv term)

let response_base request_id evaluation_prefix query_kind payload elapsed_ms = [
  "request_id", `String request_id;
  "evaluation_prefix", `List (List.map
    (fun tactic -> `String tactic) evaluation_prefix);
  "query_kind", `String query_kind;
  "payload", payload;
  "elapsed_ms", `Int elapsed_ms;
]

let proof_term_result attempted =
  match attempted.at_proof_term with
  | None -> (None, None)
  | Some term -> begin
      try let _, descriptor = elaborate term in (Some descriptor, None) with
      | EcCoreGoal.TcError error -> (None, Some (tc_error_json error))
      | EcProofTerm.ProofTermError error ->
          (None, Some (proof_term_error_json error))
      | EcEnv.LookupFailure error -> (None, Some (lookup_error_json error))
      | EcTyping.TyError _ as error -> (None, Some (typing_error_json error))
      | Assert_failure _ -> (None, Some (`Assoc [
          "code", `String "proof_term_cannot_concretize";
          "message", `String
            "selected head was resolved but the full proof term did not concretize";
        ]))
    end

exception Ambiguous_realization of string list

let realization_json = function
  | None -> `Null
  | Some (kind, claim) -> `Assoc [
      "kind", `String kind;
      "failure_kind", `String claim.Realizer.failure_kind;
      "payload", claim.Realizer.payload;
    ]

(* The one attempted-operation object, whatever produced its fields. *)
let attempt_json ~tactic ~outcome ~family ~resource ~argument_kinds ~side
    ~positions ~status ~failure_kind ~message ~application_head ~proof_term
    ~realization =
  `Assoc [
    "operation_family", `String family;
    "rejected_tactic", `String tactic;
    "exact_resource", `String resource;
    "argument_kinds", `List (List.map (fun x -> `String x) argument_kinds);
    "side", `String side;
    "positions", `List (List.map (fun x -> `Int x) positions);
    "native_diagnostic_status", `String status;
    "native_failure_kind", `String failure_kind;
    "native_error_message", `String message;
    "attempt_outcome", `String outcome;
    "goal_kind", `String (goal_kind ());
    "application_head", application_head;
    "proof_term", proof_term;
    "realization", realization_json realization;
  ]

let realize ~kinds ~tactic ~outcome trigger =
  if outcome <> "rejected" && outcome <> "no_progress" then None else
  match Realizer.realize Realizer_catalog.all ~kinds ~tactic trigger
  with
  | Realizer.Unrealized -> None
  | Realizer.Realized (kind, claim) -> Some (kind, claim)
  | Realizer.Ambiguous claimed -> raise (Ambiguous_realization claimed)

(* EasyCrypt parsed a supported attempted operation.  A realization explains
   a blocker, so realizers are consulted only when diagnosis found one. *)
let parsed_attempt ~kinds tactic_text observed_outcome_kind attempted =
  let proof_descriptor, _proof_error = proof_term_result attempted in
  if observed_outcome_kind <> "rejected"
     && observed_outcome_kind <> "no_progress" then
    raise (Contract_error "unsupported observed attempt outcome");
  let rejected_position = ref None in
  let diagnostic_status, execution_error =
    try ignore (run_tactics attempted.at_tactics); ("no_blocker", None) with
    | EcCoreGoal.TcError error as exn ->
        rejected_position := rejected_argument_position attempted exn;
        ("blocker", Some (tc_error_json error))
    | Assert_failure _ -> ("indeterminate", Some (`Assoc [
        "code", `String "native_assertion";
        "message", `String
          "EasyCrypt could not complete typed diagnosis of the attempted tactic";
      ]))
    | exn ->
        match tactic_rejection_json exn ~invalid_shape:
            "tactic target is not convertible to the current goal" with
        | Some error -> ("blocker", Some error)
        | None -> raise exn
  in
  if observed_outcome_kind = "rejected"
     && diagnostic_status = "no_blocker" then
    raise (Contract_error
      "manager rejected the tactic but native diagnosis accepted it");
  let application_head = application_head_result
    ?rejected_position:!rejected_position attempted in
  let realization =
    if diagnostic_status <> "blocker" then None
    else realize ~kinds ~tactic:tactic_text ~outcome:observed_outcome_kind
      (Realizer.Parsed attempted)
  in
  let failure_kind, message = match execution_error, realization with
    | Some error, Some (_, claim) ->
        (claim.Realizer.failure_kind, error_message error)
    | Some error, None ->
        (* Only a blocker is a call-applicability failure.  An indeterminate
           diagnosis keeps native_assertion, which the transport requires;
           relabelling it used to fail the whole batch. *)
        ((if diagnostic_status = "blocker" && attempted.at_family = "call"
          then "call_applicability_failure"
          else error_code error), error_message error)
    | None, _ -> ("", "")
  in
  attempt_json ~tactic:tactic_text ~outcome:observed_outcome_kind
    ~family:attempted.at_family ~resource:attempted.at_resource
    ~argument_kinds:attempted.at_argument_kinds ~side:attempted.at_side
    ~positions:attempted.at_positions ~status:diagnostic_status
    ~failure_kind ~message
    ~application_head:(Option.value ~default:`Null application_head)
    ~proof_term:(Option.value ~default:`Null proof_descriptor)
    ~realization

(* EasyCrypt could not diagnose the tactic as a supported operation: only a
   realizer that rebuilds the attempted operation can describe it. *)
let realized_attempt ~kinds tactic_text observed_outcome_kind trigger
    unrealized =
  match realize ~kinds ~tactic:tactic_text ~outcome:observed_outcome_kind
      trigger with
  | None -> Error unrealized
  | Some (kind, claim) ->
      let core = Option.get claim.Realizer.core in
      Ok (attempt_json ~tactic:tactic_text ~outcome:observed_outcome_kind
        ~family:core.Realizer.family ~resource:core.resource
        ~argument_kinds:core.argument_kinds ~side:core.side ~positions:[]
        ~status:"blocker" ~failure_kind:claim.failure_kind
        ~message:core.error_message ~application_head:core.application_head
        ~proof_term:`Null ~realization:(Some (kind, claim)))

let attempt_diagnostic_descriptor ~kinds tactic_text observed_outcome_kind =
  let error code message = `Assoc [
    "code", `String code;
    "message", `String message;
  ] in
  try
    match
      try `Parsed (parsed_attempt ~kinds tactic_text observed_outcome_kind
                     (parse_attempted_tactic tactic_text)) with
      | EcParsetree.ParseError (_, message) ->
          `Parse_error (Option.value ~default:"parse error" message)
      | Contract_error message -> `Unsupported message
    with
    | `Parsed descriptor -> Ok descriptor
    | `Parse_error message ->
        realized_attempt ~kinds tactic_text observed_outcome_kind
          (Realizer.Parse_error message) (error "parse_error" message)
    | `Unsupported message ->
        realized_attempt ~kinds tactic_text observed_outcome_kind
          (Realizer.Unsupported_shape message)
          (error "unsupported_attempt_shape" message)
  with Ambiguous_realization claimed ->
    Error (error "realization_ambiguous"
      ("several native realizers claimed the attempt: "
       ^ String.concat ", " claimed))

let exact_stage_after accepted_prefix next_attempt =
  let without_final_dot value =
    let value = String.trim value in
    let length = String.length value in
    if length = 0 || value.[length - 1] <> '.' then None
    else Some (String.trim (String.sub value 0 (length - 1)))
  in
  match without_final_dot accepted_prefix, without_final_dot next_attempt with
  | Some prefix_body, Some next_body ->
      let prefix_length = String.length prefix_body in
      if String.length next_body < prefix_length
         || String.sub next_body 0 prefix_length <> prefix_body then None
      else
        let remainder = String.trim (String.sub next_body prefix_length
          (String.length next_body - prefix_length)) in
        if String.length remainder < 2 || remainder.[0] <> ';' then None
        else
          let stage = String.trim (String.sub remainder 1
            (String.length remainder - 1)) in
          if stage = "" then None else Some (stage ^ ".")
  | _ -> None

let tactic_prefix_diagnostic_descriptor ~kinds tactic_text
    candidate_prefixes =
  let _, execution_error = native_tactic_execution tactic_text in
  match execution_error with
  | None -> raise (Contract_error
      "manager rejected the compound tactic but native diagnosis accepted it")
  | Some error ->
      let prefix_results = List.map (fun candidate ->
        let effect, candidate_error = native_tactic_execution candidate in
        candidate, effect, candidate_error
      ) candidate_prefixes in
      let accepted = List.filter_map (fun (candidate, effect, _) ->
        if effect = "rejected" then None else Some candidate
      ) prefix_results in
      let boundary_error = match List.find_opt (fun (_, effect, _) ->
        effect = "rejected"
      ) prefix_results with
        | Some (_, _, Some candidate_error) -> candidate_error
        | _ -> error
      in
      let rec longest_contiguous last remaining =
        match remaining with
        | (candidate, effect, _) :: tail when effect <> "rejected" ->
            longest_contiguous (Some (candidate, effect)) tail
        | _ -> last
      in
      let rec contiguous_accepted remaining =
        match remaining with
        | (candidate, effect, _) :: tail when effect <> "rejected" ->
            candidate :: contiguous_accepted tail
        | _ -> []
      in
      let boundary_tactic = match longest_contiguous None prefix_results with
        | None -> None
        | Some (accepted_prefix, _) ->
            let rec next_attempt remaining = match remaining with
              | [] -> tactic_text
              | (candidate, _, _) :: tail ->
                  if candidate <> accepted_prefix then next_attempt tail
                  else match tail with
                    | (next_candidate, _, _) :: _ -> next_candidate
                    | [] -> tactic_text
            in
            exact_stage_after accepted_prefix (next_attempt prefix_results)
      in
      let boundary_attempt =
        match accepted = contiguous_accepted prefix_results,
            longest_contiguous None prefix_results, boundary_tactic with
        | true, Some (accepted_prefix, effect), Some tactic
            when effect = "accepted_no_progress"
              || effect = "accepted_changed" -> begin
            try
              let boundary_proof = run_tactics
                (parse_tactics accepted_prefix) in
              with_diagnostic_proof boundary_proof (fun () ->
                match attempt_diagnostic_descriptor ~kinds tactic "rejected" with
                | Ok descriptor -> Some descriptor
                | Error _ -> None)
            with _ -> None
          end
        | _ -> None
      in
      `Assoc [
        "rejected_tactic", `String tactic_text;
        "candidate_prefixes", `List (List.map
          (fun item -> `String item) candidate_prefixes);
        "prefix_effects", `List (List.map
          (fun (_, effect, _) -> `String effect) prefix_results);
        "accepted_prefixes", `List (List.map
          (fun item -> `String item) accepted);
        "boundary_tactic", Option.value ~default:(`String "")
          (Option.map (fun item -> `String item) boundary_tactic);
        "boundary_attempt", Option.value ~default:`Null boundary_attempt;
        "native_failure_kind", `String (error_code error);
        "native_error_message", `String (error_message error);
        "boundary_failure_kind", `String (error_code boundary_error);
        "boundary_error_message", `String (error_message boundary_error);
        "goal_kind", `String (goal_kind ());
      ]

type selected_binding_branch = {
  sbb_replay : EcProofTerm.pt_ev;
  sbb_arguments_rev : string list;
}

let copy_proof_term (value : EcProofTerm.pt_ev) =
  { value with ptev_env = EcProofTerm.copy value.ptev_env }

let one_application_argument selected_resource candidate =
  let module_argument = "(<: " ^ candidate ^ ")" in
  match parse_exact_term "apply"
      (selected_resource ^ " " ^ module_argument) with
  | Logical term -> begin match term.EcParsetree.fp_args with
      | [argument] -> (module_argument, argument)
      | _ -> raise (Contract_error
          "module candidate did not parse as one proof-term argument")
    end
  | Call _ -> raise (Contract_error
      "module candidate unexpectedly parsed as a call argument")

let selected_head selected_resource =
  match parse_exact_term "apply" selected_resource with
  | Logical term ->
      let tcenv = current_tcenv1 () in
      let head = EcProofTerm.tc1_process_pterm
        tcenv term.EcParsetree.fp_head in
      (term, head)
  | Call _ -> raise (Contract_error
      "selected application binding set requires a logical proof term")

let count_module_slots (head : EcProofTerm.pt_ev) =
  let add_local identifier local_kind hyps =
    try EcEnv.LDecl.add_local identifier local_kind hyps with
    | EcEnv.LDecl.LdeclError _ -> hyps
  in
  let extend_hyps hyps identifier = function
    | GTty ty -> add_local identifier (EcBaseLogic.LD_var (ty, None)) hyps
    | GTmodty module_restriction ->
        add_local identifier
          (EcBaseLogic.LD_modty module_restriction) hyps
    | GTmem memory_type ->
        add_local identifier (EcBaseLogic.LD_mem memory_type) hyps
  in
  let rec count hyps formula value =
    match EcProofTyping.destruct_product ~reduce:false
        hyps formula with
    | None -> value
    | Some (`Imp (_, conclusion)) -> count hyps conclusion value
    | Some (`Forall (identifier, generic_type, conclusion)) ->
        count (extend_hyps hyps identifier generic_type) conclusion
          (if match generic_type with GTmodty _ -> true | _ -> false
           then value + 1 else value)
  in
  count head.ptev_env.pte_hy head.ptev_ax 0

let matches_current_goal (value : EcProofTerm.pt_ev) =
  let value = copy_proof_term value in
  try
    EcProofTerm.pf_form_match
      ~mode:EcMatching.fmdelta value.ptev_env
      ~ptn:value.ptev_ax
      (EcCoreGoal.FApi.tc1_goal (current_tcenv1 ()));
    true
  with
  | EcCoreGoal.TcError _
  | EcProofTerm.ProofTermError _
  | EcEnv.LookupFailure _
  | EcTyping.TyError _
  | EcMatching.MatchFailure
  | Assert_failure _ -> false

let typed_selected_bindings selected_resource module_candidates head =
  let maximum_typed_bindings = 64 in
  let maximum_candidate_checks = 4096 in
  let overflow = ref false in
  let candidate_checks = ref 0 in
  let completed = ref [] in
  let record (branch : selected_binding_branch) =
    completed := branch :: !completed;
    if List.length !completed > maximum_typed_bindings then
      overflow := true
  in
  (* EasyCrypt's [apply] matches the goal against the conclusion after any
     number of consumed premises, so once a module argument is bound every
     product boundary, including one before a later module binder, is itself
     a candidate form. Only a form that matches the goal is kept, so forms
     that cannot apply do not use up the bound; a kept form is still checked
     and executed before it counts. *)
  let at_boundary (branch : selected_binding_branch) =
    if List.exists (fun argument -> argument <> "_") branch.sbb_arguments_rev
       && matches_current_goal branch.sbb_replay
    then record { branch with sbb_replay = copy_proof_term branch.sbb_replay }
  in
  let rec visit (branch : selected_binding_branch) =
    if !overflow then () else
    match EcProofTyping.destruct_product ~reduce:false
        branch.sbb_replay.ptev_env.pte_hy branch.sbb_replay.ptev_ax with
    | None -> record branch
    | Some (`Imp _) ->
        at_boundary branch;
        let replay = EcProofTerm.apply_pterm_to_hole branch.sbb_replay in
        visit { sbb_replay = replay;
          sbb_arguments_rev = "_" :: branch.sbb_arguments_rev; }
    | Some (`Forall (_, GTmodty _, _)) ->
        at_boundary branch;
        List.iter (fun candidate ->
          if not !overflow then begin
            if !candidate_checks >= maximum_candidate_checks then
              overflow := true
            else begin
              incr candidate_checks;
            let replay = copy_proof_term branch.sbb_replay in
            try
              let source_argument = one_application_argument
                selected_resource candidate in
              let rendered_argument, source_argument = source_argument in
              let typed_argument = EcProofTerm.process_pterm_arg
                replay source_argument in
              let replay = EcProofTerm.apply_pterm_to_arg
                replay typed_argument in
              visit { sbb_replay = replay;
                sbb_arguments_rev =
                  rendered_argument :: branch.sbb_arguments_rev; }
            with
            | EcCoreGoal.TcError _
            | EcProofTerm.ProofTermError _
            | EcEnv.LookupFailure _
            | EcParsetree.ParseError _
            | EcTyping.TyError _
            | Contract_error _
            | Assert_failure _ -> ()
            end
          end)
          module_candidates
    | Some (`Forall _) ->
        at_boundary branch;
        let replay = EcProofTerm.apply_pterm_to_hole branch.sbb_replay in
        visit { sbb_replay = replay;
          sbb_arguments_rev = "_" :: branch.sbb_arguments_rev; }
  in
  visit { sbb_replay = copy_proof_term head; sbb_arguments_rev = []; };
  (!overflow, !candidate_checks, List.length !completed,
    if !overflow then [] else List.rev !completed)

let checked_selected_application operation selected_resource
    (branch : selected_binding_branch) =
  let replay = copy_proof_term branch.sbb_replay in
  try
    EcProofTerm.pf_form_match
      ~mode:EcMatching.fmdelta replay.ptev_env
      ~ptn:replay.ptev_ax
      (EcCoreGoal.FApi.tc1_goal (current_tcenv1 ()));
    if not (EcProofTerm.can_concretize replay.ptev_env) then None else
    let proof, formula = EcProofTerm.concretize replay in
    let arguments = List.rev branch.sbb_arguments_rev in
    let application_term = selected_resource ^ " "
      ^ String.concat " " arguments in
    let candidate_tactic = operation ^ " (" ^ application_term ^ ")." in
    match native_tactic_execution candidate_tactic with
    | "accepted_changed", None ->
        let parsed = match parse_exact_term operation application_term with
          | Logical term -> term
          | Call _ -> raise (Contract_error
              "selected binding unexpectedly parsed as a call")
        in
        let descriptor = descriptor_json
          (current_tcenv1 ()) parsed proof formula in
        Some (`Assoc [
          "application_term", `String application_term;
          "candidate_tactic", `String candidate_tactic;
          "tactic_effect", `String "accepted_changed";
          "descriptor", descriptor;
        ])
    | _ -> None
  with
  | EcCoreGoal.TcError _
  | EcProofTerm.ProofTermError _
  | EcEnv.LookupFailure _
  | EcParsetree.ParseError _
  | EcTyping.TyError _
  | EcMatching.MatchFailure
  | Contract_error _
  | Assert_failure _ -> None

let selected_application_binding_set_descriptor operation selected_resource
    module_candidates =
  if operation <> "apply" && operation <> "exact" then
    raise (Contract_error
      "selected binding search supports only apply/exact");
  let _parsed, head = selected_head selected_resource in
  let module_slot_count = count_module_slots head in
  if module_slot_count < 1 then
    raise (Contract_error "selected theorem has no module slots");
  let overflow, candidate_check_count, typed_binding_count, typed_bindings =
    typed_selected_bindings selected_resource module_candidates head in
  (* A branch's module assignment: its arguments up to the last module. *)
  let assignment (branch : selected_binding_branch) =
    let rec drop_holes = function
      | "_" :: rest -> drop_holes rest
      | arguments -> arguments
    in
    List.rev (drop_holes branch.sbb_arguments_rev)
  in
  let checked_pairs = if overflow then [] else List.filter_map
    (fun branch -> Option.map (fun result -> (assignment branch, result))
      (checked_selected_application operation selected_resource branch))
    typed_bindings in
  (* EasyCrypt's [apply] also unfolds definitions and tries iff and negation
     views, which the depth forms above do not. If it accepts the shortest
     form of an assignment that has no checked completion, the checked set is
     not all that [apply] accepts, so no zero or unique claim is made. *)
  let apply_accepts arguments =
    let application_term =
      selected_resource ^ " " ^ String.concat " " arguments in
    match native_tactic_execution
        (operation ^ " (" ^ application_term ^ ").") with
    | "accepted_changed", _ -> true
    | _ -> false
    | exception ((Out_of_memory | Stack_overflow) as exn) -> raise exn
    | exception _ -> false
  in
  let completed_assignments = List.map fst checked_pairs in
  let unchecked_assignments = List.filter
    (fun arguments -> not (List.mem arguments completed_assignments))
    (List.sort_uniq compare (List.map assignment typed_bindings)) in
  (* At most 32 extra executions; beyond that the set is not claimed. *)
  let maximum_refutation_runs = 32 in
  let refutation_exceeds_bound =
    (not overflow)
    && List.length unchecked_assignments > maximum_refutation_runs in
  let unsearched_form_accepted = (not overflow)
    && (not refutation_exceeds_bound)
    && List.exists apply_accepts unchecked_assignments in
  let checked =
    if unsearched_form_accepted || refutation_exceeds_bound then [] else
    List.sort_uniq (fun left right ->
      String.compare
        (json_string "application_term" left)
        (json_string "application_term" right))
      (List.map snd checked_pairs) in
  let checked_count = List.length checked in
  let ppe = EcPrinting.PPEnv.ofenv
    (EcScope.env (EcCommands.current ())) in
  let resolved = resolved_head head.ptev_pt in
  let complete =
    not overflow && not unsearched_form_accepted
    && not refutation_exceeds_bound in
  `Assoc [
    "operation", `String operation;
    "selected_resource", `String selected_resource;
    "resolved_head", head_json ppe resolved;
    "module_slot_count", `Int module_slot_count;
    "candidate_module_term_count", `Int (List.length module_candidates);
    "candidate_check_count", `Int candidate_check_count;
    "typed_binding_count", `Int typed_binding_count;
    "checked_completion_count", `Int checked_count;
    "population_complete", `Bool complete;
    "checked_completions", `List (
      if complete && checked_count <= 4 then checked else []);
    "reason", `String (
      if overflow then "native_binding_search_exceeds_bound"
      else if refutation_exceeds_bound
      then "native_binding_refutation_exceeds_bound"
      else if unsearched_form_accepted
      then "native_apply_accepts_unsearched_form"
      else "");
  ]

(* Mirrors MAX_NATIVE_NAMESPACE_SPELLINGS in the Python contracts. *)
let max_namespace_spellings = 16

(* One agent-written tactic whose head name does not resolve.  EasyCrypt
   enumerates every lemma or axiom of the environment whose last name
   component equals the written basename (required theories, clones and
   earlier declarations alike; abstract theories contribute nothing) and
   spells each one, as [locate] does, with its shortest name that resolves back
   to the same path in the goal context, where an unqualified name that is a
   hypothesis denotes the hypothesis; a shadowed path that no name resolves to
   is not usable and is skipped.  Each spelling replaces only the head of the
   agent's tactic,
   whose operation and argument text are unchanged, and the complete tactic
   runs at the current goal, so placeholders that only the goal determines are
   instantiated by the operation itself.  A written name that already denotes
   a lemma or a local of the goal is not a namespace problem and yields no
   spellings.  An over-bound population reports no verdicts. *)
let namespace_spelling_set_descriptor operation arguments written_name =
  if not (List.mem operation ["apply"; "exact"; "call"; "conseq"]) then
    raise (Contract_error "namespace spelling set has an unsupported operation");
  let written =
    try EcSymbols.qsymbol_of_string written_name with
    | Invalid_argument _ ->
        raise (Contract_error "namespace spelling name is invalid")
  in
  let hyps = EcCoreGoal.FApi.tc1_hyps (current_tcenv1 ()) in
  let env = EcEnv.LDecl.toenv hyps in
  (* Proof-term heads resolve an unqualified name to a hypothesis first. *)
  let names_hypothesis (qualifier, name) =
    qualifier = [] && EcEnv.LDecl.hyp_exists name hyps
  in
  let written_name_resolves =
    names_hypothesis written
    || Option.is_some (EcEnv.Ax.lookup_opt written env)
  in
  let resolves path name =
    (not (names_hypothesis name))
    && match EcEnv.Ax.lookup_opt name env with
       | Some (found, _) -> EcPath.p_equal path found
       | None -> false
  in
  let ppe = EcPrinting.PPEnv.ofenv env in
  let spell path =
    let long, short = EcPrinting.shorten_path ppe resolves path in
    let name = Option.value ~default:long short in
    if resolves path name
    then Some (path, EcSymbols.string_of_qsymbol name)
    else None
  in
  let population =
    if written_name_resolves then [] else
    EcEnv.Ax.all ~check:(fun path _ -> EcPath.basename path = snd written) env
    |> List.map fst
    |> List.sort_uniq EcPath.p_compare
    |> List.filter_map spell
    |> List.sort (fun (_, left) (_, right) -> String.compare left right)
  in
  let complete = List.length population <= max_namespace_spellings in
  let check (path, spelling) =
    let application_term =
      if arguments = "" then spelling else spelling ^ " " ^ arguments in
    let candidate_tactic = operation ^ " (" ^ application_term ^ ")." in
    (* One candidate's failure is its own rejection, except resource
       exhaustion, which aborts the batch rather than shrink the population. *)
    let effect =
      try fst (native_tactic_execution candidate_tactic) with
      | (Out_of_memory | Stack_overflow) as exn -> raise exn
      | _ -> "rejected"
    in
    `Assoc [
      "candidate_head", `String spelling;
      "resolved_identity", `String (EcPath.tostring path);
      "application_term", `String application_term;
      "candidate_tactic", `String candidate_tactic;
      "tactic_effect", `String effect;
    ]
  in
  `Assoc [
    "operation", `String operation;
    "arguments", `String arguments;
    "written_name", `String written_name;
    "written_name_resolves", `Bool written_name_resolves;
    "population_count", `Int (List.length population);
    "population_complete", `Bool complete;
    "spellings", `List (if complete then List.map check population else []);
  ]

let run_query_at_current_proof request evaluation_prefix =
  let request_id = json_string "request_id" request in
  let query_kind = json_string "query_kind" request in
  let payload = request |> member "payload" in
  let started = Sys.time () in
  let finish fields =
    let elapsed_ms = int_of_float ((Sys.time () -. started) *. 1000.0) in
    `Assoc (fields @ response_base request_id evaluation_prefix query_kind
      payload elapsed_ms)
  in
  let rejected error = finish [
    "status", `String "rejected";
    "result_formula", `String "";
    "descriptor", `Assoc [];
    "structured_error", error;
  ] in
  if query_kind = "proof_term_elaboration" then begin
    let operation = json_string "operation" payload in
    let application_term = json_string "application_term" payload in
    try
      let term = parse_exact_term operation application_term in
      let formula, descriptor = elaborate term in
      finish ["status", `String "accepted"; "result_formula", `String formula;
        "descriptor", descriptor; "structured_error", `Assoc [];]
    with
    | EcCoreGoal.TcError error -> rejected (tc_error_json error)
    | EcProofTerm.ProofTermError error ->
        rejected (proof_term_error_json error)
    | EcEnv.LookupFailure error -> rejected (lookup_error_json error)
    | EcTyping.TyError _ as error -> rejected (typing_error_json error)
    | EcParsetree.ParseError (_, message) -> rejected (`Assoc [
        "code", `String "parse_error";
        "message", `String (Option.value ~default:"parse error" message);])
  end else if query_kind = "selected_application_binding_set" then begin
    let operation = json_string "operation" payload in
    let selected_resource = json_string "selected_resource" payload in
    let module_candidates = json_string_list "module_candidates" payload in
    try
      let descriptor = selected_application_binding_set_descriptor
        operation selected_resource module_candidates in
      finish ["status", `String "accepted"; "result_formula", `String "";
        "descriptor", descriptor; "structured_error", `Assoc [];]
    with
    | EcCoreGoal.TcError error -> rejected (tc_error_json error)
    | EcProofTerm.ProofTermError error ->
        rejected (proof_term_error_json error)
    | EcEnv.LookupFailure error -> rejected (lookup_error_json error)
    | EcParsetree.ParseError (_, message) -> rejected (`Assoc [
        "code", `String "parse_error";
        "message", `String (Option.value ~default:"parse error" message);])
    | Contract_error message -> rejected (`Assoc [
        "code", `String "contract_error";
        "message", `String message;])
  end else if query_kind = "namespace_spelling_set" then begin
    let operation = json_string "operation" payload in
    let arguments = json_string "arguments" payload in
    let written_name = json_string "written_name" payload in
    try
      let descriptor = namespace_spelling_set_descriptor
        operation arguments written_name in
      finish ["status", `String "accepted"; "result_formula", `String "";
        "descriptor", descriptor; "structured_error", `Assoc [];]
    with
    | Contract_error message -> rejected (`Assoc [
        "code", `String "contract_error";
        "message", `String message;])
    | EcCoreGoal.TcError error -> rejected (tc_error_json error)
    | EcEnv.LookupFailure error -> rejected (lookup_error_json error)
  end else if query_kind = "tactic_prefix_diagnostic" then begin
    let tactic_text = json_string "rejected_tactic" payload in
    let candidate_prefixes = json_string_list "candidate_prefixes" payload in
    let kinds = json_string_list "realizer_kinds" payload in
    try
      let descriptor = tactic_prefix_diagnostic_descriptor ~kinds
        tactic_text candidate_prefixes in
      finish ["status", `String "accepted"; "result_formula", `String "";
        "descriptor", descriptor; "structured_error", `Assoc [];]
    with
    | EcParsetree.ParseError (_, message) -> rejected (`Assoc [
        "code", `String "parse_error";
        "message", `String
          (Option.value ~default:"parse error" message);])
    | Contract_error message -> rejected (`Assoc [
        "code", `String "contract_error";
        "message", `String message;])
  end else if query_kind = "attempt_diagnostic" then begin
    let tactic_text = json_string "rejected_tactic" payload in
    let observed_outcome_kind = json_string "observed_outcome_kind" payload in
    let kinds = json_string_list "realizer_kinds" payload in
    match attempt_diagnostic_descriptor ~kinds tactic_text
        observed_outcome_kind with
    | Ok descriptor -> finish [
        "status", `String "accepted";
        "result_formula", `String "";
        "descriptor", descriptor;
        "structured_error", `Assoc [];
      ]
    | Error error -> rejected error
  end else raise (Contract_error "unsupported semantic query kind")

let run_query request =
  let evaluation_prefix = json_string_list "evaluation_prefix" request in
  match evaluation_prefix with
  | [] -> run_query_at_current_proof request evaluation_prefix
  | _ ->
      let tactics = List.flatten (List.map parse_tactics evaluation_prefix) in
      let boundary_proof = run_tactics tactics in
      with_diagnostic_proof boundary_proof (fun () ->
        run_query_at_current_proof request evaluation_prefix)

(* A requested realization kind without a realizer here means the compiler's
   features and [Realizer_catalog.all] disagree.  Skipping it would silently
   disable that feature's realizations, so the whole batch fails instead. *)
let check_realizer_kinds requests =
  List.iter (fun request ->
    let payload = request |> member "payload" in
    match payload |> member "realizer_kinds" with
    | `Null -> ()
    | _ ->
        List.iter (fun kind ->
          if not (List.exists (fun realizer -> realizer.Realizer.kind = kind)
                    Realizer_catalog.all)
          then raise (Contract_error ("no native realizer for kind " ^ kind)))
          (json_string_list "realizer_kinds" payload))
    requests

let run request =
  if request |> member "schema_version" |> to_int <> 20 then
    raise (Contract_error "unsupported request schema_version");
  if request |> member "kind" |> to_string <>
      "native_semantic_batch_request" then
    raise (Contract_error "unsupported request kind");
  let batch_id = json_string "batch_id" request in
  let context_file = json_string "context_file" request in
  let history_file = json_string "history_file" request in
  let include_dirs = json_string_list "include_dirs" request in
  let requests = request |> member "requests" |> to_list in
  if List.length requests < 1 || List.length requests > 8 then
    raise (Contract_error "invalid native semantic batch size");
  let request_ids = List.map (json_string "request_id") requests in
  if List.length request_ids <>
      List.length (List.sort_uniq String.compare request_ids) then
    raise (Contract_error "duplicate native semantic request IDs");
  check_realizer_kinds requests;
  initialize include_dirs;
  process_file context_file;
  process_file history_file;
  let goal = goal_text () in
  `Assoc [
    "schema_version", `Int 20;
    "kind", `String "native_semantic_batch_result";
    "batch_id", `String batch_id;
    "goal_before", `String goal;
    "results", `List (List.map run_query requests);
  ]

let () =
  let response =
    try run (Yojson.Safe.from_channel stdin) with
    | Contract_error message -> `Assoc [
      "schema_version", `Int 20;
        "kind", `String "native_semantic_batch_result";
        "status", `String "contract_error";
        "message", `String message;
      ]
    | exn -> `Assoc [
      "schema_version", `Int 20;
        "kind", `String "native_semantic_batch_result";
        "status", `String "adapter_error";
        "message", `String (Printexc.to_string exn);
      ]
  in
  output_string stdout "SHANNON_NATIVE_SEMANTIC_V1:";
  Yojson.Safe.to_channel stdout response;
  output_char stdout '\n';
  flush stdout
