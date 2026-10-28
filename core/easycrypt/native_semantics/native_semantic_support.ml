(* Shared typed helpers for the native semantic companion and its realizers.

   Everything here is feature-neutral: the proof the queries run against,
   parsing, structured EasyCrypt errors, typed descriptors of an attempted
   operation, and tactic execution at the current proof.  A feature's
   realizer may use these; it never adds to them. *)

open EcLib
open EcAst
open EcFol
open EcCoreGoal

(* The semantic companion reaches the shared adapter helpers only through
   this module, so the [current_proof] below, which honours the diagnostic
   proof override, is the only one in scope there. *)
include Native_adapter_common

(* Native semantic queries are read-only with respect to the manager-owned
   session, but a compound-boundary query must diagnose one suffix in the
   scratch proof produced by its accepted prefix.  Keep that proof local to
   this companion process and make every existing typed helper consume the
   same explicit override. *)
let reconstructed_current_proof = current_proof
let diagnostic_proof_override = ref None

let current_proof () =
  match !diagnostic_proof_override with
  | Some proof -> proof
  | None -> reconstructed_current_proof ()

let current_tcenv1 () = EcCoreGoal.tcenv1_of_proof (current_proof ())

let with_diagnostic_proof proof callback =
  let previous = !diagnostic_proof_override in
  diagnostic_proof_override := Some proof;
  Fun.protect
    ~finally:(fun () -> diagnostic_proof_override := previous)
    callback

type parsed_term =
  | Logical of EcParsetree.ppterm
  | Call of EcParsetree.call_info EcParsetree.gppterm

let located_desc value = value.EcLocation.pl_desc

(* The lexer raises its own exception for an illegal character or an
   unterminated comment or string. Report it as the parse error it is, so one
   lexical slip rejects its own query instead of aborting the whole batch. The
   lexer reads bytes, so its message may hold one byte of a multi-byte
   character; that message is escaped to stay valid UTF-8. *)
let parse_sentences text =
  try EcIo.(parseall (from_string text)) with
  | EcLexer.LexicalError (location, message) ->
      let message =
        if String.is_valid_utf_8 message then message
        else String.escaped message
      in
      raise (EcParsetree.ParseError
        (Option.value ~default:EcLocation._dummy location, Some message))

let logical_term_of_conseq
    (term : EcParsetree.conseq_ppterm) : EcParsetree.ppterm =
  match term.EcParsetree.fp_head with
  | EcParsetree.FPNamed (head, types) -> {
      EcParsetree.fp_mode = term.EcParsetree.fp_mode;
      fp_head = EcParsetree.FPNamed (head, types);
      fp_args = term.EcParsetree.fp_args;
    }
  | EcParsetree.FPCut _ -> raise (Contract_error
      "consequence binding repair requires one named theorem head")

let string_of_argkind kind =
  EcUserMessages.PTermError.string_of_argkind kind

let proof_term_error_json (((_, _, _), kind) as error) =
  let code, details = match kind with
    | EcProofTerm.AE_WrongArgKind (actual, expected) ->
        ("wrong_argument_kind", [
          "actual_kind", `String (string_of_argkind actual);
          "expected_kind", `String (string_of_argkind expected);
        ])
    | EcProofTerm.AE_CannotInfer -> ("cannot_infer", [])
    | EcProofTerm.AE_CannotInferMod -> ("cannot_infer_module", [])
    | EcProofTerm.AE_NotFunctional -> ("not_functional", [])
    | EcProofTerm.AE_InvalidArgForm (EcProofTerm.IAF_Mismatch _) ->
        ("formula_type_mismatch", [])
    | EcProofTerm.AE_InvalidArgForm (EcProofTerm.IAF_TyError _) ->
        ("invalid_formula_argument", [])
    | EcProofTerm.AE_InvalidArgMod _ -> ("invalid_module_argument", [])
    | EcProofTerm.AE_InvalidArgProof _ -> ("proof_argument_mismatch", [])
    | EcProofTerm.AE_InvalidArgModRestr _ ->
        ("module_restriction_failure", [])
  in
  `Assoc (("code", `String code) ::
    ("message", `String (Format.asprintf "%a"
      EcUserMessages.PTermError.pp_pterm_apperror error)) :: details)

let lookup_error_json error =
  let kind = match error with
    | `XPath _ -> "procedure"
    | `MPath _ -> "module"
    | `Path _ -> "path"
    | `QSymbol _ -> "symbol"
    | `AbsStmt _ -> "abstract_statement"
  in
  `Assoc [
    "code", `String "lookup_failure";
    "lookup_kind", `String kind;
    "message", `String (Format.asprintf "%a" EcEnv.pp_lookup_failure error);
  ]

let typing_error_json error = `Assoc [
  "code", `String "typing_error";
  "message", `String (exception_text error);
]

let tc_error_json error =
  match error.EcCoreGoal.tc_message with
  | EcCoreGoal.TCEExn (EcProofTerm.ProofTermError proof_error) ->
      proof_term_error_json proof_error
  | EcCoreGoal.TCEExn (EcEnv.LookupFailure lookup_error) ->
      lookup_error_json lookup_error
  | EcCoreGoal.TCEExn exn -> `Assoc [
      "code", `String "native_exception";
      "message", `String (exception_text exn);
    ]
  | EcCoreGoal.TCEUser (value, render) -> `Assoc [
      "code", `String "native_user_error";
      "message", `String (render value);
    ]

let pp printer value = Format.asprintf "%a" printer value

let type_text ppe ty = pp (EcPrinting.pp_type ppe) ty

let rec module_path_json ppe module_path =
  let top_kind, top_identity = match module_path.EcPath.m_top with
    | `Local identifier -> "local", EcIdent.name identifier
    | `Concrete (path, suffix) ->
        "concrete", EcPath.tostring (EcPath.poappend path suffix)
  in
  `Assoc [
    "term", `String (pp (EcPrinting.pp_topmod ppe) module_path);
    "top_kind", `String top_kind;
    "top_identity", `String top_identity;
    "arguments", `List (List.map
      (module_path_json ppe) module_path.EcPath.m_args);
  ]

let relation_operator path =
  if EcPath.p_equal path EcCoreLib.CI_Int.p_int_le ||
     EcPath.p_equal path EcCoreLib.CI_Real.p_real_le ||
     EcPath.p_equal path EcCoreLib.CI_Xreal.p_xle then
    Some "<="
  else if EcPath.p_equal path EcCoreLib.CI_Int.p_int_lt ||
          EcPath.p_equal path EcCoreLib.CI_Real.p_real_lt then
    Some "<"
  else
    None

let formula_boundary_json ppe formula =
  match EcFol.sform_of_form formula with
  | SFop ((path, _), [left; _]) -> begin
      match relation_operator path, EcFol.sform_of_form left with
      | Some _, SFpr probability -> Some (`Assoc [
          "role", `String "relation_left_probability";
          "procedure_identity", `String (
            EcPath.x_tostring probability.pr_fun);
          "module", module_path_json ppe probability.pr_fun.EcPath.x_top;
        ])
      | _ -> None
    end
  | _ -> None

let shallow_formula_json ppe formula =
  let boundary = match formula_boundary_json ppe formula with
    | None -> []
    | Some value -> ["boundary", value]
  in
  let base kind fields = `Assoc (
    ("kind", `String kind) ::
    ("text", `String (pp (EcPrinting.pp_form ppe) formula)) ::
    ("type", `String (type_text ppe formula.f_ty)) ::
    (boundary @ fields))
  in
  match EcFol.sform_of_form formula with
  | SFbdHoareF judgment -> base "bounded_hoare_function" [
      "procedure", `String (EcPath.x_tostring judgment.bhf_f);
      "comparison", `String (EcPrinting.string_of_hcmp judgment.bhf_cmp);
      "lossless", `Bool (
           EcFol.f_equal EcFol.f_true (bhf_pr judgment).inv
        && EcFol.f_equal EcFol.f_true (bhf_po judgment).inv
        && EcFol.f_equal EcFol.f_r1 (bhf_bd judgment).inv
        && judgment.bhf_cmp = FHeq);
    ]
  | SFhoareF judgment -> base "hoare_function" [
      "procedure", `String (EcPath.x_tostring judgment.hf_f);
    ]
  | SFpr probability -> base "probability" [
      "procedure", `String (EcPath.x_tostring probability.pr_fun);
    ]
  | SFimp _ -> base "implication" []
  | SFquant _ -> base "quantifier" []
  | SFtrue -> base "true" []
  | SFfalse -> base "false" []
  | _ -> base "formula" []

let input_argument_source_spelling argument =
  match argument.EcLocation.pl_desc with
  | EcParsetree.EA_form formula -> begin
      match located_desc formula with
      | EcParsetree.PFident (name, _) ->
          EcSymbols.string_of_qsymbol name.EcLocation.pl_desc
      | _ -> ""
    end
  | _ -> ""

let input_argument_json ?(rejected = false) index argument =
  let kind, hole = match argument.EcLocation.pl_desc with
    | EcParsetree.EA_none -> "hole", true
    | EcParsetree.EA_form _ -> "formula", false
    | EcParsetree.EA_mem _ -> "memory", false
    | EcParsetree.EA_mod _ -> "module", false
    | EcParsetree.EA_proof _ -> "proof", false
    | EcParsetree.EA_tactic _ -> "proof_tactic", false
  in
  `Assoc [
    "position", `Int index;
    "syntax_kind", `String kind;
    "explicit_hole", `Bool hole;
    "source_spelling", `String (input_argument_source_spelling argument);
    "rejected", `Bool rejected;
  ]

let input_argument_kind argument =
  match argument.EcLocation.pl_desc with
  | EcParsetree.EA_none -> "hole"
  | EcParsetree.EA_form _ -> "formula"
  | EcParsetree.EA_mem _ -> "memory"
  | EcParsetree.EA_mod _ -> "module"
  | EcParsetree.EA_proof _ -> "proof"
  | EcParsetree.EA_tactic _ -> "proof_tactic"

let rec resolved_head = function
  | PTQuant (_, proof) -> resolved_head proof
  | PTApply { pt_head = PTTerm proof; _ } -> resolved_head proof
  | PTApply { pt_head; _ } -> pt_head

let rec head_json ppe = function
  | PTGlobal (path, types) -> `Assoc [
      "kind", `String "global";
      "identity", `String (EcPath.tostring path);
      "type_arguments", `List (List.map
        (fun ty -> `String (type_text ppe ty)) types);
    ]
  | PTLocal identifier -> `Assoc [
      "kind", `String "local";
      "identity", `String (EcIdent.name identifier);
      "type_arguments", `List [];
    ]
  | PTTerm proof -> head_json ppe (resolved_head proof)
  | PTCut _ -> raise (Contract_error "cut proof-term heads are unsupported")
  | PTHandle _ -> raise (Contract_error "handle proof-term heads are unsupported")

let rec proof_hole_formula = function
  | PTQuant (_, proof) -> proof_hole_formula proof
  | PTApply { pt_head = PTCut (formula, _); pt_args = [] } -> Some formula
  | PTApply { pt_head = PTTerm proof; pt_args = [] } -> proof_hole_formula proof
  | _ -> None

let is_proof_hole = function
  | PASub None -> true
  | PASub (Some proof) -> Option.is_some (proof_hole_formula proof)
  | _ -> false

let expected_argument_json ppe = function
  | `Imp (premise, _) -> `Assoc [
      "kind", `String "proof";
      "name", `String "";
      "formula", shallow_formula_json ppe premise;
    ]
  | `Forall (identifier, generic_type, _) -> begin
      let kind, expected = match generic_type with
        | GTty ty -> "formula", type_text ppe ty
        | GTmodty (module_type, _) ->
            "module", pp (EcPrinting.pp_modtype1 ppe) module_type
        | GTmem memory_type ->
            "memory", pp (EcPrinting.pp_memtype ppe) memory_type
      in
      `Assoc [
        "kind", `String kind;
        "name", `String (EcIdent.name identifier);
        "type", `String expected;
      ]
    end

let application_slot_json ppe index product =
  let expected = match product with
    | `Imp _ -> begin
        try expected_argument_json ppe product with
        | Assert_failure _ -> `Assoc [
            "kind", `String "proof";
            "name", `String "";
            "type", `String "bool";
          ]
      end
    | `Forall _ -> expected_argument_json ppe product
  in
  match expected with
  | `Assoc fields -> `Assoc (("position", `Int index) :: fields)
  | _ -> raise (Contract_error "native application slot is not an object")

let describe_application_head ?rejected_position ppe parsed
    (head : EcProofTerm.pt_ev) =
  let add_local identifier local_kind hyps =
    try EcEnv.LDecl.add_local identifier local_kind hyps with
    | EcEnv.LDecl.LdeclError _ -> hyps
  in
  let extend_context _ppe hyps identifier = function
    | GTty ty ->
        let hyps = add_local identifier (EcBaseLogic.LD_var (ty, None)) hyps in
        (EcPrinting.PPEnv.ofenv (EcEnv.LDecl.toenv hyps), hyps)
    | GTmodty ((module_type, _) as module_restriction) ->
        let _ = module_type in
        let hyps = add_local identifier
          (EcBaseLogic.LD_modty module_restriction) hyps in
        (EcPrinting.PPEnv.ofenv (EcEnv.LDecl.toenv hyps), hyps)
    | GTmem memory_type ->
        let hyps = add_local identifier
          (EcBaseLogic.LD_mem memory_type) hyps in
        (EcPrinting.PPEnv.ofenv (EcEnv.LDecl.toenv hyps), hyps)
  in
  let rec slots index ppe hyps formula collected =
    (* The selected head is already a typed proof term.  Reducing its result
       while walking module quantifiers is both unnecessary and less robust:
       upstream reduction contains assertions for some higher-order module
       binders.  A head descriptor describes the product that is present; it
       must not normalize the theorem into a different search problem. *)
    match (try EcProofTyping.destruct_product ~reduce:false hyps formula with
      | Assert_failure _ -> raise (Contract_error
          (Printf.sprintf "native application-head product %d asserted" index))) with
    | None -> (List.rev collected, formula, ppe, hyps)
    | Some product ->
        let descriptor = application_slot_json ppe index product in
        let ppe, hyps, conclusion = match product with
          | `Imp (_, conclusion) -> (ppe, hyps, conclusion)
          | `Forall (identifier, generic_type, conclusion) ->
              let ppe, hyps = try extend_context
                ppe hyps identifier generic_type with
                | Assert_failure _ -> raise (Contract_error
                    (Printf.sprintf
                      "native application-head context %d asserted" index)) in
              (ppe, hyps, conclusion)
        in
        slots (index + 1) ppe hyps conclusion
          (descriptor :: collected)
  in
  let slot_values, result, result_ppe, result_hyps =
    slots 1 ppe head.ptev_env.pte_hy head.ptev_ax [] in
  (* Applying the head, EasyCrypt unfolds definitions to find further
     products, which the slots above do not; say whether the result still
     unfolds into one, since the slots are then not all the arguments. *)
  let unfolds_to_more_slots =
    try Option.is_some (EcProofTyping.destruct_product result_hyps result) with
    | (Out_of_memory | Stack_overflow) as exn -> raise exn
    | _ -> true
  in
  let resolved = try resolved_head head.ptev_pt with
    | Assert_failure _ -> raise (Contract_error
        "native application-head resolution asserted") in
  let input_mode, input_values = match parsed with
    | Logical term -> (term.EcParsetree.fp_mode, term.EcParsetree.fp_args)
    | Call term -> (term.EcParsetree.fp_mode, term.EcParsetree.fp_args)
  in
  `Assoc [
    "resolved_head", (try head_json ppe resolved with
      | Assert_failure _ -> raise (Contract_error
          "native application-head printing asserted"));
    "input_mode", `String (match input_mode with
      | `Explicit -> "explicit" | `Implicit -> "implicit");
    "input_arguments", `List (List.mapi
      (fun index argument -> input_argument_json
        ~rejected:(rejected_position = Some (index + 1))
        (index + 1) argument)
      input_values);
    (* With implicit arguments on, EasyCrypt inserts inferred arguments
       before the written ones, so written positions are not slot positions. *)
    "implicits_enabled", `Bool
      (EcScope.Options.get_implicits (EcCommands.current ()));
    "slots", `List slot_values;
    "unfolds_to_more_slots", `Bool unfolds_to_more_slots;
    "result", (try shallow_formula_json result_ppe result with
      | Assert_failure _ -> raise (Contract_error
          "native application-head result printing asserted"));
  ]

let error_code = function
  | `Assoc fields -> begin match List.assoc_opt "code" fields with
      | Some (`String code) -> code
      | _ -> "native_error"
    end
  | _ -> "native_error"

let error_message = function
  | `Assoc fields -> begin match List.assoc_opt "message" fields with
      | Some (`String message) -> message
      | _ -> ""
    end
  | _ -> ""

let side_string = function
  | None -> ""
  | Some `Left -> "left"
  | Some `Right -> "right"

let term_resource term = match term.EcParsetree.fp_head with
  | EcParsetree.FPNamed (name, _) ->
      EcSymbols.string_of_qsymbol name.EcLocation.pl_desc
  | EcParsetree.FPCut _ -> ""

let goal_kind () =
  match EcFol.sform_of_form (EcCoreGoal.FApi.tc1_goal (current_tcenv1 ())) with
  | SFbdHoareF _ -> "bounded_hoare_function"
  | SFhoareF _ -> "hoare_function"
  | SFequivF _ -> "equiv_function"
  | SFequivS _ -> "equiv_statement"
  | SFpr _ -> "probability"
  | SFimp _ -> "implication"
  | SFquant _ -> "quantifier"
  | _ -> "formula"

type attempted_tactic = {
  at_tactics : EcParsetree.ptactic list;
  at_family : string;
  at_resource : string;
  at_argument_kinds : string list;
  at_side : string;
  at_positions : int list;
  at_proof_term : parsed_term option;
  at_change_formula : EcParsetree.pformula option;
}

(* EasyCrypt locates an argument-kind error, or an argument with no product
   left to apply to, at the rejected argument itself, so an equal location
   names that top-level argument. An error inside a nested proof term matches
   no top-level argument. *)
let rejected_argument_position attempted = function
  | EcCoreGoal.TcError {
      EcCoreGoal.tc_message = EcCoreGoal.TCEExn (EcProofTerm.ProofTermError
        (_, (EcProofTerm.AE_WrongArgKind _ | EcProofTerm.AE_NotFunctional)));
      tc_location = Some { EcCoreGoal.plc_loc = location; _ }; _ } ->
      let arguments = match attempted.at_proof_term with
        | Some (Logical term) -> term.EcParsetree.fp_args
        | Some (Call term) -> term.EcParsetree.fp_args
        | None -> []
      in
      let rec find position = function
        | [] -> None
        | (argument : _ EcLocation.located) :: rest ->
            let argument_location = argument.EcLocation.pl_loc in
            if argument_location.EcLocation.loc_bchar
                 = location.EcLocation.loc_bchar
               && argument_location.EcLocation.loc_echar
                 = location.EcLocation.loc_echar
            then Some position
            else find (position + 1) rest
      in
      find 1 arguments
  | _ -> None

let application_head_result ?rejected_position attempted =
  match attempted.at_proof_term with
  | None -> None
  | Some parsed -> begin
      try
        let tcenv = current_tcenv1 () in
        let head = try match parsed with
          | Logical term ->
              EcProofTerm.tc1_process_pterm tcenv term.EcParsetree.fp_head
          | Call term ->
              EcProofTerm.tc1_process_pterm_cut
                ~prcut:(fun _ ->
                  raise (Contract_error
                    "inline call specifications have no named head"))
                tcenv term.EcParsetree.fp_head
          with Assert_failure _ ->
            raise (Contract_error "native application-head processing asserted")
        in
        let environment = EcScope.env (EcCommands.current ()) in
        let ppe = EcPrinting.PPEnv.ofenv environment in
        Some (try describe_application_head ?rejected_position
                    ppe parsed head with
          | Assert_failure _ -> raise (Contract_error
              "native application-head description asserted"))
      with
      | EcCoreGoal.TcError _
      | EcProofTerm.ProofTermError _
      | EcEnv.LookupFailure _
      | EcTyping.TyError _
      | Contract_error _ -> None
    end

let parse_tactics tactic_text =
  let globals = parse_sentences tactic_text in
  match globals with
    | [{ EcParsetree.gl_action = action; _ }] -> begin
        match located_desc action with
        | EcParsetree.Gtactics (`Actual (_, tactics)) -> tactics
        | _ -> raise (Contract_error "request did not parse as a tactic")
      end
    | _ -> raise (Contract_error "request did not parse as one global action")

let parse_attempted_tactic tactic_text =
  let tactics = parse_tactics tactic_text in
  let tactic = match tactics with
    | [{ EcParsetree.pt_core = core; pt_intros = [] }] -> core
    | _ -> raise (Contract_error "request did not parse as one plain tactic")
  in
  match located_desc tactic with
  | EcParsetree.Plogic (EcParsetree.Papply (`Apply ([term], kind), None))
      when kind = `Apply || kind = `Exact ->
      { at_tactics = tactics;
        at_family = if kind = `Apply then "apply" else "exact";
        at_resource = term_resource term;
        at_argument_kinds = List.map input_argument_kind term.EcParsetree.fp_args;
        at_side = ""; at_positions = [];
        at_proof_term = Some (Logical term); at_change_formula = None; }
  | EcParsetree.PPhl (EcParsetree.Pcall (side, term)) ->
      { at_tactics = tactics; at_family = "call";
        at_resource = term_resource term;
        at_argument_kinds = List.map input_argument_kind term.EcParsetree.fp_args;
        at_side = side_string side; at_positions = [];
        at_proof_term = (match term.EcParsetree.fp_head with
          | EcParsetree.FPNamed _ -> Some (Call term)
          | EcParsetree.FPCut _ -> None);
        at_change_formula = None; }
  | EcParsetree.PPhl
      (EcParsetree.Pconseq ([], (Some term, None, None))) ->
      let term = logical_term_of_conseq term in
      { at_tactics = tactics; at_family = "conseq";
        at_resource = term_resource term;
        at_argument_kinds = List.map input_argument_kind term.EcParsetree.fp_args;
        at_side = ""; at_positions = [];
        at_proof_term = Some (Logical term); at_change_formula = None; }
  | EcParsetree.Plogic (EcParsetree.Pchange formula) ->
      { at_tactics = tactics; at_family = "change"; at_resource = "";
        at_argument_kinds = ["formula"]; at_side = ""; at_positions = [];
        at_proof_term = None; at_change_formula = Some formula; }
  | EcParsetree.Plogic (EcParsetree.Prewrite ([(None, argument)], None)) ->
      begin match located_desc argument with
      | EcParsetree.RWRw (options, [(`LtoR, term)])
          when options.EcParsetree.side = `LtoR
            && options.EcParsetree.repeat = None
            && options.EcParsetree.occurrence = None
            && options.EcParsetree.match_ = None
            && term.EcParsetree.fp_args = [] ->
          let resource = term_resource term in
          if resource = "" then
            raise (Contract_error "rewrite requires one named lemma")
          else
            { at_tactics = tactics; at_family = "rewrite";
              at_resource = resource;
              at_argument_kinds = ["rewrite_lemma"];
              at_side = ""; at_positions = [];
              at_proof_term = None; at_change_formula = None; }
      | _ -> raise (Contract_error
          "rewrite recovery requires one plain left-to-right named lemma")
      end
  | _ -> raise (Contract_error "unsupported attempted operation family")

let run_tactics tactics =
  let scope = EcCommands.current () in
  let ttenv = {
    EcHiGoal.tt_provers = (fun _ -> EcProvers.dft_prover_infos);
    EcHiGoal.tt_smtmode = `Strict;
    EcHiGoal.tt_implicits = EcScope.Options.get_implicits scope;
    EcHiGoal.tt_oldip = EcScope.Options.get scope "oldip";
    EcHiGoal.tt_redlogic = EcScope.Options.get scope "redlogic";
  } in
  snd (EcHiTacticals.process ttenv tactics (current_proof ()))

(* The tactic misused the local context: a name clash, an unknown local, or
   a hypothesis that cannot be cleared.  EasyCrypt raises these outside
   TcError. *)
let local_context_error_json exn =
  let code = match exn with
    | EcEnv.LDecl.LdeclError _ -> "local_declaration_error"
    | _ -> "clear_error"
  in
  `Assoc [
    "code", `String code;
    "message", `String (exception_text exn);
  ]

(* EasyCrypt's ordinary ways of rejecting a tactic, as structured errors.
   [invalid_shape] explains InvalidGoalShape at the calling site.  Anything
   else (assertions, contract errors, adapter bugs) stays with the caller.
   Located errors (e.g. a [pose] name clash) are unwrapped, as EasyCrypt's
   own [t_try] does. *)
let rec tactic_rejection_json ~invalid_shape = function
  | EcLocation.LocError (_, error) -> tactic_rejection_json ~invalid_shape error
  | EcCoreGoal.TcError error -> Some (tc_error_json error)
  | EcProofTerm.ProofTermError error -> Some (proof_term_error_json error)
  | EcEnv.LookupFailure error -> Some (lookup_error_json error)
  | EcTyping.TyError _ as error -> Some (typing_error_json error)
  | EcCoreGoal.InvalidGoalShape -> Some (`Assoc [
      "code", `String "invalid_goal_shape";
      "message", `String invalid_shape;
    ])
  | (EcEnv.LDecl.LdeclError _ | EcCoreGoal.ClearError _) as exn ->
      Some (local_context_error_json exn)
  | _ -> None

let native_tactic_execution tactic =
  let before = current_proof () in
  try
    let after = run_tactics (parse_tactics tactic) in
    let same_open_goal left right =
      left.EcCoreGoal.g_hyps == right.EcCoreGoal.g_hyps
      && EcFol.f_equal left.EcCoreGoal.g_concl right.EcCoreGoal.g_concl
    in
    let effect =
      if List.equal same_open_goal
          (EcCoreGoal.all_opened before) (EcCoreGoal.all_opened after)
      then "accepted_no_progress"
      else "accepted_changed"
    in
    effect, None
  with
  | EcParsetree.ParseError (_, message) -> "rejected", Some (`Assoc [
      "code", `String "parse_error";
      "message", `String (Option.value ~default:"parse error" message);
    ])
  | Contract_error message -> "rejected", Some (`Assoc [
      "code", `String "contract_error";
      "message", `String message;
    ])
  | Assert_failure _ -> "rejected", Some (`Assoc [
      "code", `String "native_assertion";
      "message", `String
        "EasyCrypt could not complete the compound tactic";
    ])
  | exn ->
      match tactic_rejection_json exn ~invalid_shape:
          "tactic target is not convertible to the current goal" with
      | Some error -> "rejected", Some error
      | None -> raise exn

let native_tactic_execution_error tactic =
  snd (native_tactic_execution tactic)

let native_preflight_candidate tactic =
  Option.is_none (native_tactic_execution_error tactic)

let phl_goal_form () =
  match EcFol.sform_of_form (EcCoreGoal.FApi.tc1_goal (current_tcenv1 ())) with
  | SFequivF _ -> Some "function"
  | SFequivS _ -> Some "statement"
  | _ -> None

let substring_at text index needle =
  let text_length = String.length text in
  let needle_length = String.length needle in
  index >= 0 && index + needle_length <= text_length &&
  let rec equal offset =
    offset = needle_length ||
    (text.[index + offset] = needle.[offset] && equal (offset + 1))
  in equal 0

let contains_substring text needle =
  let rec scan index =
    index + String.length needle <= String.length text &&
    (substring_at text index needle || scan (index + 1))
  in String.length needle > 0 && scan 0

let top_level_positions text needle =
  let text_length = String.length text in
  let needle_length = String.length needle in
  if needle_length = 0 then None else
  let rec scan index parens braces brackets positions =
    if index >= text_length then
      if parens = 0 && braces = 0 && brackets = 0
      then Some (List.rev positions) else None
    else if parens = 0 && braces = 0 && brackets = 0
      && substring_at text index needle then
        scan (index + needle_length) parens braces brackets
          (index :: positions)
    else
      let parens', braces', brackets' = match text.[index] with
        | '(' -> parens + 1, braces, brackets
        | ')' -> parens - 1, braces, brackets
        | '{' -> parens, braces + 1, brackets
        | '}' -> parens, braces - 1, brackets
        | '[' -> parens, braces, brackets + 1
        | ']' -> parens, braces, brackets - 1
        | _ -> parens, braces, brackets
      in
      if parens' < 0 || braces' < 0 || brackets' < 0 then None
      else scan (index + 1) parens' braces' brackets' positions
  in scan 0 0 0 0 []
