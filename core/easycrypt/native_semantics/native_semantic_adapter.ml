(* Narrow read-only native semantic-query probe.

   The process reconstructs an EasyCrypt proof state from a manager-owned
   extracted context and committed tactic prefix, then asks EcProofTerm to
   elaborate one bounded ordered batch of exact application terms after one
   replay.  The caller must bind paths, hashes,
   StateRef, no-mutation checks, artifact authority, and runtime/library build
   identity.  This executable owns none of those harness policies. *)

open EcLib
open EcAst
open EcFol
open EcCoreGoal
open Yojson.Safe.Util
open Native_adapter_common

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

let parse_exact_term operation application_term =
  let tactic = operation ^ " (" ^ application_term ^ ")." in
  let globals = EcIo.(parseall (from_string tactic)) in
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

let tc_error_json error =
  match error.EcCoreGoal.tc_message with
  | EcCoreGoal.TCEExn (EcProofTerm.ProofTermError proof_error) ->
      proof_term_error_json proof_error
  | EcCoreGoal.TCEExn (EcEnv.LookupFailure lookup_error) ->
      lookup_error_json lookup_error
  | EcCoreGoal.TCEExn exn -> `Assoc [
      "code", `String "native_exception";
      "message", `String (Printexc.to_string exn);
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

let input_argument_json index argument =
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

let describe_application_head ppe parsed (head : EcProofTerm.pt_ev) =
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
    | None -> (List.rev collected, formula, ppe)
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
  let slot_values, result, result_ppe =
    slots 1 ppe head.ptev_env.pte_hy head.ptev_ax [] in
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
      (fun index argument -> input_argument_json (index + 1) argument)
      input_values);
    "slots", `List slot_values;
    "result", (try shallow_formula_json result_ppe result with
      | Assert_failure _ -> raise (Contract_error
          "native application-head result printing asserted"));
  ]

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

let application_head_result attempted =
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
        Some (try describe_application_head ppe parsed head with
          | Assert_failure _ -> raise (Contract_error
              "native application-head description asserted"))
      with
      | EcCoreGoal.TcError _
      | EcProofTerm.ProofTermError _
      | EcEnv.LookupFailure _
      | Contract_error _ -> None
    end

let parse_tactics tactic_text =
  let globals = EcIo.(parseall (from_string tactic_text)) in
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

let real_le_view formula =
  match EcFol.sform_of_form formula with
  | SFop ((path, _), [left; right])
      when EcPath.p_equal path EcCoreLib.CI_Real.p_real_le ->
      Some (left, right)
  | _ -> None

let real_lt_view formula =
  match EcFol.sform_of_form formula with
  | SFop ((path, _), [left; right])
      when EcPath.p_equal path EcCoreLib.CI_Real.p_real_lt ->
      Some (left, right)
  | _ -> None

let int_le_view formula =
  match EcFol.sform_of_form formula with
  | SFop ((path, _), [left; right])
      when EcPath.p_equal path EcCoreLib.CI_Int.p_int_le ->
      Some (left, right)
  | _ -> None

let parse_change_target tactic_text =
  let globals = EcIo.(parseall (from_string tactic_text)) in
  match globals with
  | [{ EcParsetree.gl_action = action; _ }] -> begin
      match located_desc action with
      | EcParsetree.Gtactics
          (`Actual (_, [{ EcParsetree.pt_core = core; pt_intros = [] }])) ->
          begin match located_desc core with
          | EcParsetree.Plogic (EcParsetree.Pchange formula) -> formula
          | _ -> raise (Contract_error "bridge probe is not a change formula")
          end
      | _ -> raise (Contract_error "bridge probe is not one plain tactic")
    end
  | _ -> raise (Contract_error "bridge probe is not one global action")

let relation_bridge_json source_operation relation_family certificate_family
    failure_kind intermediate intermediate_type source_target_present target_convertible
    target_right_convertible =
  let candidate = "apply (" ^ certificate_family ^ " " ^ intermediate
    ^ "); first last." in
  `Assoc [
    "source_operation", `String source_operation;
    "relation_family", `String relation_family;
    "intermediate_text", `String intermediate;
    "intermediate_type", `String intermediate_type;
    "candidate_tactic", `String candidate;
    "failure_kind", `String failure_kind;
    "source_target_present", `Bool source_target_present;
    "source_target_convertible_to_current_goal", `Bool target_convertible;
    "source_target_right_convertible_to_current_right",
      `Bool target_right_convertible;
  ]

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
  | EcCoreGoal.TcError error -> "rejected", Some (tc_error_json error)
  | EcProofTerm.ProofTermError error ->
      "rejected", Some (proof_term_error_json error)
  | EcEnv.LookupFailure error -> "rejected", Some (lookup_error_json error)
  | EcCoreGoal.InvalidGoalShape -> "rejected", Some (`Assoc [
      "code", `String "invalid_goal_shape";
      "message", `String
        "tactic target is not convertible to the current goal";
    ])
  | EcTyping.TyError _ as error -> "rejected", Some (`Assoc [
      "code", `String "typing_error";
      "message", `String (Printexc.to_string error);
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

let native_tactic_execution_error tactic =
  snd (native_tactic_execution tactic)

let native_preflight_candidate tactic =
  Option.is_none (native_tactic_execution_error tactic)

let pure_tail_rewrite_result attempted =
  if attempted.at_family <> "rewrite" || attempted.at_resource = "" then None
  else
    let local_hypotheses =
      (EcEnv.LDecl.tohyps
        (EcCoreGoal.FApi.tc1_hyps (current_tcenv1 ()))).EcBaseLogic.h_local in
    let candidates = List.filter_map (fun (identifier, local_kind) ->
      match local_kind with
      | EcBaseLogic.LD_hyp _ ->
          let target = EcIdent.name identifier in
          let tactic = "rewrite " ^ attempted.at_resource ^ " in "
            ^ target ^ "." in
          (* A local equality can often rewrite itself.  That is an executable
             but circular target repair, so it is not part of the candidate
             population. *)
          if target <> attempted.at_resource
            && native_preflight_candidate tactic
          then Some (target, tactic)
          else None
      | _ -> None) local_hypotheses in
    match candidates with
    | [(target, tactic)] -> Some (`Assoc [
        "source_operation", `String "rewrite";
        "selected_resource", `String attempted.at_resource;
        "target_kind", `String "hypothesis";
        "target_name", `String target;
        "candidate_tactic", `String tactic;
        "failure_kind", `String "rewrite_target_mismatch";
        "accepted_target_count", `Int 1;
      ])
    | _ -> None

let relation_bridge_choice_json left intermediate right intermediate_type =
  let specifications = [
    ("ler_lt_trans", "<=", "<");
    ("ltr_le_trans", "<", "<=");
    ("ltr_trans", "<", "<");
  ] in
  let choices = List.map (fun (family, left_relation, right_relation) ->
    let tactic = "apply (" ^ family ^ " " ^ intermediate
      ^ "); first last." in
    if not (native_preflight_candidate tactic) then
      raise (Contract_error "strict relation bridge candidate did not preflight");
    `Assoc [
      "certificate_family", `String family;
      "left_relation", `String left_relation;
      "right_relation", `String right_relation;
      "candidate_tactic", `String tactic;
    ]) specifications in
  `Assoc [
    "source_operation", `String "transitivity";
    "relation_family", `String "real_lt";
    "goal_left_text", `String left;
    "intermediate_text", `String intermediate;
    "goal_right_text", `String right;
    "intermediate_type", `String intermediate_type;
    "failure_kind", `String "formula_transitivity_surface_mismatch";
    "choices", `List choices;
  ]

let phl_goal_form () =
  match EcFol.sform_of_form (EcCoreGoal.FApi.tc1_goal (current_tcenv1 ())) with
  | SFequivF _ -> Some "function"
  | SFequivS _ -> Some "statement"
  | _ -> None

let phl_side_string = function
  | `Left -> "left"
  | `Right -> "right"

let phl_transitivity_attempt_descriptor tactic_text observed_outcome_kind =
  if observed_outcome_kind <> "rejected"
     && observed_outcome_kind <> "no_progress" then None else
  try
    let tactics = parse_tactics tactic_text in
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
              "statement", phl_side_string side
        end
      | _ -> raise (Contract_error "not a PHL transitivity tactic")
    in
    match phl_goal_form () with
    | None -> None
    | Some current_goal_form when current_goal_form = attempted_form -> None
    | Some current_goal_form ->
        let execution_error =
          try ignore (run_tactics tactics); None with
          | EcCoreGoal.TcError error -> Some (tc_error_json error)
          | EcProofTerm.ProofTermError error ->
              Some (proof_term_error_json error)
          | EcEnv.LookupFailure error -> Some (lookup_error_json error)
          | EcCoreGoal.InvalidGoalShape -> Some (`Assoc [
              "code", `String "invalid_goal_shape";
              "message", `String
                "PHL transitivity form does not match the current goal";
            ])
          | Assert_failure _ -> None
        in
        begin match execution_error with
        | None -> None
        | Some error -> Some (`Assoc [
            "operation_family", `String "transitivity";
            "rejected_tactic", `String tactic_text;
            "exact_resource", `String "";
            "argument_kinds", `List [`String ("phl_" ^ attempted_form)];
            "side", `String side;
            "positions", `List [];
            "native_diagnostic_status", `String "blocker";
            "native_failure_kind",
              `String "phl_transitivity_boundary_mismatch";
            "native_error_message", `String (error_message error);
            "attempt_outcome", `String observed_outcome_kind;
            "goal_kind", `String (goal_kind ());
            "application_head", `Null;
            "proof_term", `Null;
            "relation_bridge", `Null;
            "relation_bridge_choice", `Null;
            "phl_transitivity_boundary", `Assoc [
              "source_operation", `String "transitivity";
              "attempted_form", `String attempted_form;
              "current_goal_form", `String current_goal_form;
              "side", `String side;
              "failure_kind",
                `String "phl_transitivity_boundary_mismatch";
            ];
            "eager_while_dialect", `Null;
            "pure_tail_rewrite", `Null;
            "intro_pattern_realization", `Null;
            "application_syntax_repair", `Null;
          ])
        end
  with
  | EcParsetree.ParseError _
  | Contract_error _ -> None

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

let application_module_syntax_failure_descriptor tactic_text
    observed_outcome_kind parse_message =
  if observed_outcome_kind <> "rejected"
     && observed_outcome_kind <> "no_progress" then None else
  match call_module_syntax_candidate tactic_text with
  | None -> None
  | Some (resource, module_term, candidate_application, candidate_tactic) ->
      begin try
        let attempted = parse_attempted_tactic candidate_tactic in
        match attempted.at_family, attempted.at_resource,
            attempted.at_argument_kinds, application_head_result attempted with
        | "call", selected, ("module" :: _ as argument_kinds), Some head
            when selected = resource && first_application_slot_is_module head ->
            Some (`Assoc [
              "operation_family", `String "call";
              "rejected_tactic", `String tactic_text;
              "exact_resource", `String resource;
              "argument_kinds", `List [];
              "side", `String "";
              "positions", `List [];
              "native_diagnostic_status", `String "blocker";
              "native_failure_kind",
                `String "application_module_argument_syntax";
              "native_error_message", `String parse_message;
              "attempt_outcome", `String observed_outcome_kind;
              "goal_kind", `String (goal_kind ());
              "application_head", head;
              "proof_term", `Null;
              "relation_bridge", `Null;
              "relation_bridge_choice", `Null;
              "phl_transitivity_boundary", `Null;
              "eager_while_dialect", `Null;
              "pure_tail_rewrite", `Null;
              "intro_pattern_realization", `Null;
              "application_syntax_repair", `Assoc [
                "source_operation", `String "call";
                "selected_resource", `String resource;
                "module_argument_position", `Int 1;
                "module_term_text", `String module_term;
                "candidate_application_term", `String candidate_application;
                "candidate_tactic", `String candidate_tactic;
                "candidate_argument_kinds", `List (List.map
                  (fun value -> `String value) argument_kinds);
                "failure_kind",
                  `String "application_module_argument_syntax";
                "resolved_candidate_count", `Int 1;
              ];
            ])
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

let intro_pattern_failure_descriptor tactic_text observed_outcome_kind =
  if observed_outcome_kind <> "rejected"
     && observed_outcome_kind <> "no_progress" then None else
  try
    let tactics = parse_tactics tactic_text in
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
    let span = match single_outer_bracket_span_after_intro tactic_text with
      | Some span -> span
      | None -> raise (Contract_error
          "intro-pattern repair could not isolate one selected case tree")
    in
    let replacement = "[# " ^ String.concat " " binder_names ^ "]" in
    let candidate_tactic = replace_text_span tactic_text span replacement in
    let execution_error =
      try ignore (run_tactics tactics); None with
      | EcCoreGoal.TcError error -> Some (tc_error_json error)
      | EcCoreGoal.InvalidGoalShape -> Some (`Assoc [
          "code", `String "invalid_goal_shape";
          "message", `String
            "the selected intro pattern does not fit the current goal";
        ])
    in
    begin match execution_error with
    | Some error when native_preflight_candidate candidate_tactic ->
        Some (`Assoc [
          "operation_family", `String "intro_pattern";
          "rejected_tactic", `String tactic_text;
          "exact_resource", `String "";
          "argument_kinds", `List [`String "ordered_named_binders"];
          "side", `String "";
          "positions", `List [];
          "native_diagnostic_status", `String "blocker";
          "native_failure_kind",
            `String "intro_pattern_structure_mismatch";
          "native_error_message", `String (error_message error);
          "attempt_outcome", `String observed_outcome_kind;
          "goal_kind", `String (goal_kind ());
          "application_head", `Null;
          "proof_term", `Null;
          "relation_bridge", `Null;
          "relation_bridge_choice", `Null;
          "phl_transitivity_boundary", `Null;
          "eager_while_dialect", `Null;
          "pure_tail_rewrite", `Null;
          "intro_pattern_realization", `Assoc [
            "source_operation", `String "intro_pattern";
            "surface_operation", `String surface_operation;
            "attempted_pattern_kind", `String "nested_case";
            "binder_names", `List
              (List.map (fun name -> `String name) binder_names);
            "candidate_tactic", `String candidate_tactic;
            "failure_kind", `String "intro_pattern_structure_mismatch";
            "selected_pattern_count", `Int 1;
          ];
          "application_syntax_repair", `Null;
        ])
    | _ -> None
    end
  with
  | EcParsetree.ParseError _
  | EcCoreGoal.TcError _
  | EcTyping.TyError _
  | EcEnv.LookupFailure _
  | Contract_error _ -> None

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

let eager_while_candidate_json invariant =
  `Assoc [
    "invariant_text", `String invariant;
    "candidate_tactic", `String ("eager while (" ^ invariant ^ ").");
  ]

let eager_while_descriptor_json tactic_text observed_outcome_kind
    attempted_shape failure_kind native_error_message candidates =
  `Assoc [
    "operation_family", `String "eager";
    "rejected_tactic", `String tactic_text;
    "exact_resource", `String "";
    "argument_kinds", `List [`String (if attempted_shape = "invariant"
      then "formula" else "eager_while_contract")];
    "side", `String "";
    "positions", `List [];
    "native_diagnostic_status", `String "blocker";
    "native_failure_kind", `String failure_kind;
    "native_error_message", `String native_error_message;
    "attempt_outcome", `String observed_outcome_kind;
    "goal_kind", `String (goal_kind ());
    "application_head", `Null;
    "proof_term", `Null;
    "relation_bridge", `Null;
    "relation_bridge_choice", `Null;
    "phl_transitivity_boundary", `Null;
    "eager_while_dialect", `Assoc [
      "source_operation", `String "eager";
      "eager_subform", `String "while";
      "attempted_shape", `String attempted_shape;
      "failure_kind", `String failure_kind;
      "candidates", `List (List.map eager_while_candidate_json candidates);
    ];
    "pure_tail_rewrite", `Null;
    "intro_pattern_realization", `Null;
    "application_syntax_repair", `Null;
  ]

let eager_while_parse_failure_descriptor tactic_text observed_outcome_kind
    parse_message =
  if observed_outcome_kind <> "rejected"
     && observed_outcome_kind <> "no_progress" then None else
  match phl_goal_form (), eager_while_contract_formulas tactic_text with
  | Some "statement", Some (precondition, postcondition) ->
      let candidates = unique_strings [precondition; postcondition]
        |> List.filter (fun invariant -> native_preflight_candidate
          ("eager while (" ^ invariant ^ ").")) in
      if candidates = [] && not (native_preflight_candidate
          "eager while (true).") then None
      else Some (eager_while_descriptor_json tactic_text observed_outcome_kind
        "explicit_statement_contract" "eager_while_dialect_mismatch"
        parse_message candidates)
  | _ -> None

let eager_while_guard_failure_descriptor tactic_text observed_outcome_kind =
  if observed_outcome_kind <> "rejected"
     && observed_outcome_kind <> "no_progress" then None else
  try
    let tactics = parse_tactics tactic_text in
    let core = match tactics with
      | [{ EcParsetree.pt_core = core; pt_intros = [] }] -> core
      | _ -> raise (Contract_error "eager while is not one plain tactic")
    in
    match located_desc core, phl_goal_form () with
    | EcParsetree.PPhl (EcParsetree.Peager_while _), Some "statement" ->
        let execution_error =
          try ignore (run_tactics tactics); None with
          | EcCoreGoal.TcError error -> Some (tc_error_json error)
          | EcCoreGoal.InvalidGoalShape -> Some (`Assoc [
              "code", `String "invalid_goal_shape";
              "message", `String "eager while is not valid at this boundary";
            ])
          | Assert_failure _ -> None
        in
        begin match execution_error with
        | Some error when contains_substring (error_message error)
            "both while guards must be syntactically equal" ->
            Some (eager_while_descriptor_json tactic_text observed_outcome_kind
              "invariant" "eager_while_guard_mismatch"
              (error_message error) [])
        | _ -> None
        end
    | _ -> None
  with
  | EcParsetree.ParseError _
  | Contract_error _ -> None

let change_relation_bridge_result attempted =
  match attempted.at_change_formula with
  | None -> None
  | Some parsed -> begin
      try
        let tc = current_tcenv1 () in
        let target = EcProofTyping.tc1_process_formula tc parsed in
        let current = EcCoreGoal.FApi.tc1_goal tc in
        match real_le_view target, real_le_view current with
        | Some (intermediate, target_right), Some (_, current_right) ->
            let hyps = EcCoreGoal.FApi.tc1_hyps tc in
            let target_convertible = EcReduction.is_conv
              ~ri:EcReduction.full_compat hyps target current in
            let right_convertible = EcReduction.is_conv
              ~ri:EcReduction.full_compat hyps target_right current_right in
            if target_convertible || not right_convertible then None else
            let environment = EcScope.env (EcCommands.current ()) in
            let ppe = EcPrinting.PPEnv.ofenv environment in
            Some (relation_bridge_json "change" "real_le" "ler_trans"
              "change_target_not_convertible"
              (pp (EcPrinting.pp_form ppe) intermediate)
              (type_text ppe intermediate.f_ty)
              true false true)
        | _ -> None
      with
      | EcCoreGoal.TcError _
      | EcTyping.TyError _
      | EcEnv.LookupFailure _ -> None
    end

let transitivity_argument tactic_text =
  let prefix = "transitivity " in
  let prefix_length = String.length prefix in
  let length = String.length tactic_text in
  if length <= prefix_length + 1
     || not (String.starts_with ~prefix tactic_text)
     || tactic_text.[length - 1] <> '.' then None
  else
    let value = String.sub tactic_text prefix_length
      (length - prefix_length - 1) |> String.trim in
    if value = ""
       || String.contains value ';'
       || String.contains value '\n'
       || String.contains value '\r'
       || String.contains value '"' then None
    else Some value

let change_argument tactic_text =
  let prefix = "change " in
  let prefix_length = String.length prefix in
  let length = String.length tactic_text in
  if length <= prefix_length + 1
     || not (String.starts_with ~prefix tactic_text)
     || tactic_text.[length - 1] <> '.' then None
  else
    let value = String.sub tactic_text prefix_length
      (length - prefix_length - 1) |> String.trim in
    if value = ""
       || String.contains value ';'
       || String.contains value '\n'
       || String.contains value '\r'
       || String.contains value '"' then None
    else Some value

let transitivity_attempt_descriptor tactic_text observed_outcome_kind
    parse_message =
  if observed_outcome_kind <> "rejected"
     && observed_outcome_kind <> "no_progress" then None else
  match transitivity_argument tactic_text with
  | None -> None
  | Some argument -> begin
      try
        let tc = current_tcenv1 () in
        match real_le_view (EcCoreGoal.FApi.tc1_goal tc),
            real_lt_view (EcCoreGoal.FApi.tc1_goal tc),
            int_le_view (EcCoreGoal.FApi.tc1_goal tc) with
        | None, None, None -> None
        | Some (_, current_right), None, None ->
            let environment = EcScope.env (EcCommands.current ()) in
            let ppe = EcPrinting.PPEnv.ofenv environment in
            let probe = "change (" ^ argument ^ " <= "
              ^ (pp (EcPrinting.pp_form ppe) current_right) ^ ")." in
            let parsed = parse_change_target probe in
            let target = EcProofTyping.tc1_process_formula tc parsed in
            begin match real_le_view target with
            | None -> None
            | Some (intermediate, target_right) ->
                let hyps = EcCoreGoal.FApi.tc1_hyps tc in
                if not (EcReduction.is_conv ~ri:EcReduction.full_compat
                    hyps target_right current_right) then None else
                let bridge = relation_bridge_json "transitivity"
                  "real_le" "ler_trans"
                  "formula_transitivity_surface_mismatch"
                  argument (type_text ppe intermediate.f_ty)
                  false false false in
                Some (`Assoc [
                  "operation_family", `String "transitivity";
                  "rejected_tactic", `String tactic_text;
                  "exact_resource", `String "";
                  "argument_kinds", `List [`String "formula"];
                  "side", `String "";
                  "positions", `List [];
                  "native_diagnostic_status", `String "blocker";
                  "native_failure_kind",
                    `String "formula_transitivity_surface_mismatch";
                  "native_error_message", `String parse_message;
                  "attempt_outcome", `String observed_outcome_kind;
                  "goal_kind", `String (goal_kind ());
                  "application_head", `Null;
                  "proof_term", `Null;
                  "relation_bridge", bridge;
                  "relation_bridge_choice", `Null;
                  "phl_transitivity_boundary", `Null;
                  "eager_while_dialect", `Null;
                  "pure_tail_rewrite", `Null;
                  "intro_pattern_realization", `Null;
                  "application_syntax_repair", `Null;
                ])
            end
        | None, Some (current_left, current_right), None ->
            let environment = EcScope.env (EcCommands.current ()) in
            let ppe = EcPrinting.PPEnv.ofenv environment in
            let probe = "change (" ^ argument ^ " < "
              ^ (pp (EcPrinting.pp_form ppe) current_right) ^ ")." in
            let parsed = parse_change_target probe in
            let target = EcProofTyping.tc1_process_formula tc parsed in
            begin match real_lt_view target with
            | None -> None
            | Some (intermediate, target_right) ->
                let hyps = EcCoreGoal.FApi.tc1_hyps tc in
                if not (EcReduction.is_conv ~ri:EcReduction.full_compat
                    hyps target_right current_right) then None else
                let choice = relation_bridge_choice_json
                  (pp (EcPrinting.pp_form ppe) current_left)
                  argument
                  (pp (EcPrinting.pp_form ppe) current_right)
                  (type_text ppe intermediate.f_ty) in
                Some (`Assoc [
                  "operation_family", `String "transitivity";
                  "rejected_tactic", `String tactic_text;
                  "exact_resource", `String "";
                  "argument_kinds", `List [`String "formula"];
                  "side", `String "";
                  "positions", `List [];
                  "native_diagnostic_status", `String "blocker";
                  "native_failure_kind",
                    `String "formula_transitivity_surface_mismatch";
                  "native_error_message", `String parse_message;
                  "attempt_outcome", `String observed_outcome_kind;
                  "goal_kind", `String (goal_kind ());
                  "application_head", `Null;
                  "proof_term", `Null;
                  "relation_bridge", `Null;
                  "relation_bridge_choice", choice;
                  "phl_transitivity_boundary", `Null;
                  "eager_while_dialect", `Null;
                  "pure_tail_rewrite", `Null;
                  "intro_pattern_realization", `Null;
                  "application_syntax_repair", `Null;
                ])
            end
        | None, None, Some (_, current_right) ->
            let environment = EcScope.env (EcCommands.current ()) in
            let ppe = EcPrinting.PPEnv.ofenv environment in
            let probe = "change (" ^ argument ^ " <= "
              ^ (pp (EcPrinting.pp_form ppe) current_right) ^ ")." in
            let parsed = parse_change_target probe in
            let target = EcProofTyping.tc1_process_formula tc parsed in
            begin match int_le_view target with
            | None -> None
            | Some (intermediate, target_right) ->
                let hyps = EcCoreGoal.FApi.tc1_hyps tc in
                if not (EcReduction.is_conv ~ri:EcReduction.full_compat
                    hyps target_right current_right) then None else
                let intermediate_text = argument in
                let bridge = relation_bridge_json "transitivity"
                  "int_le" "Int.lez_trans"
                  "formula_transitivity_surface_mismatch"
                  intermediate_text (type_text ppe intermediate.f_ty)
                  false false false in
                Some (`Assoc [
                  "operation_family", `String "transitivity";
                  "rejected_tactic", `String tactic_text;
                  "exact_resource", `String "";
                  "argument_kinds", `List [`String "formula"];
                  "side", `String "";
                  "positions", `List [];
                  "native_diagnostic_status", `String "blocker";
                  "native_failure_kind",
                    `String "formula_transitivity_surface_mismatch";
                  "native_error_message", `String parse_message;
                  "attempt_outcome", `String observed_outcome_kind;
                  "goal_kind", `String (goal_kind ());
                  "application_head", `Null;
                  "proof_term", `Null;
                  "relation_bridge", bridge;
                  "relation_bridge_choice", `Null;
                  "phl_transitivity_boundary", `Null;
                  "eager_while_dialect", `Null;
                  "pure_tail_rewrite", `Null;
                  "intro_pattern_realization", `Null;
                  "application_syntax_repair", `Null;
                ])
            end
        | _ -> None
      with
      | EcParsetree.ParseError _
      | EcCoreGoal.TcError _
      | EcTyping.TyError _
      | EcEnv.LookupFailure _
      | Contract_error _ -> None
    end

let change_parse_failure_descriptor tactic_text observed_outcome_kind
    parse_message =
  if observed_outcome_kind <> "rejected"
     && observed_outcome_kind <> "no_progress" then None else
  match change_argument tactic_text with
  | None -> None
  | Some target_text -> begin
      try
        let tc = current_tcenv1 () in
        let parsed = parse_change_target ("change (" ^ target_text ^ ").") in
        let target = EcProofTyping.tc1_process_formula tc parsed in
        let current = EcCoreGoal.FApi.tc1_goal tc in
        match real_le_view target, real_le_view current with
        | Some (intermediate, target_right), Some (_, current_right) ->
            let hyps = EcCoreGoal.FApi.tc1_hyps tc in
            let target_convertible = EcReduction.is_conv
              ~ri:EcReduction.full_compat hyps target current in
            let right_convertible = EcReduction.is_conv
              ~ri:EcReduction.full_compat hyps target_right current_right in
            if target_convertible || not right_convertible then None else
            let environment = EcScope.env (EcCommands.current ()) in
            let ppe = EcPrinting.PPEnv.ofenv environment in
            let bridge = relation_bridge_json "change" "real_le" "ler_trans"
              "change_target_not_convertible"
              (pp (EcPrinting.pp_form ppe) intermediate)
              (type_text ppe intermediate.f_ty)
              true false true in
            Some (`Assoc [
              "operation_family", `String "change";
              "rejected_tactic", `String tactic_text;
              "exact_resource", `String "";
              "argument_kinds", `List [`String "formula"];
              "side", `String "";
              "positions", `List [];
              "native_diagnostic_status", `String "blocker";
              "native_failure_kind", `String "change_target_not_convertible";
              "native_error_message", `String parse_message;
              "attempt_outcome", `String observed_outcome_kind;
              "goal_kind", `String (goal_kind ());
              "application_head", `Null;
              "proof_term", `Null;
              "relation_bridge", bridge;
              "relation_bridge_choice", `Null;
              "phl_transitivity_boundary", `Null;
              "eager_while_dialect", `Null;
              "pure_tail_rewrite", `Null;
              "intro_pattern_realization", `Null;
              "application_syntax_repair", `Null;
            ])
        | _ -> None
      with
      | EcParsetree.ParseError _
      | EcCoreGoal.TcError _
      | EcTyping.TyError _
      | EcEnv.LookupFailure _
      | Contract_error _ -> None
    end

let proof_term_result attempted =
  match attempted.at_proof_term with
  | None -> (None, None)
  | Some term -> begin
      try let _, descriptor = elaborate term in (Some descriptor, None) with
      | EcCoreGoal.TcError error -> (None, Some (tc_error_json error))
      | EcProofTerm.ProofTermError error ->
          (None, Some (proof_term_error_json error))
      | EcEnv.LookupFailure error -> (None, Some (lookup_error_json error))
      | Assert_failure _ -> (None, Some (`Assoc [
          "code", `String "proof_term_cannot_concretize";
          "message", `String
            "selected head was resolved but the full proof term did not concretize";
        ]))
    end

let attempt_descriptor tactic_text observed_outcome_kind attempted =
  let application_head = application_head_result attempted in
  let proof_descriptor, _proof_error = proof_term_result attempted in
  if observed_outcome_kind <> "rejected"
     && observed_outcome_kind <> "no_progress" then
    raise (Contract_error "unsupported observed attempt outcome");
  let diagnostic_status, execution_error =
    try ignore (run_tactics attempted.at_tactics); ("no_blocker", None) with
    | EcCoreGoal.TcError error -> ("blocker", Some (tc_error_json error))
    | EcProofTerm.ProofTermError error ->
        ("blocker", Some (proof_term_error_json error))
    | EcEnv.LookupFailure error ->
        ("blocker", Some (lookup_error_json error))
    | EcCoreGoal.InvalidGoalShape -> ("blocker", Some (`Assoc [
        "code", `String "invalid_goal_shape";
        "message", `String "tactic target is not convertible to the current goal";
      ]))
    | Assert_failure _ -> ("indeterminate", Some (`Assoc [
        "code", `String "native_assertion";
        "message", `String
          "EasyCrypt could not complete typed diagnosis of the attempted tactic";
      ]))
  in
  if observed_outcome_kind = "rejected"
     && diagnostic_status = "no_blocker" then
    raise (Contract_error
      "manager rejected the tactic but native diagnosis accepted it");
  let relation_bridge = change_relation_bridge_result attempted in
  let pure_tail_rewrite = pure_tail_rewrite_result attempted in
  let failure_kind, message = match execution_error with
    | Some error ->
        let kind = match attempted.at_family, relation_bridge,
            pure_tail_rewrite with
          | "call", _, _ -> "call_applicability_failure"
          | "change", Some _, _ -> "change_target_not_convertible"
          | "rewrite", _, Some _ -> "rewrite_target_mismatch"
          | _ -> error_code error
        in (kind, error_message error)
    | None -> ("", "")
  in
  `Assoc [
    "operation_family", `String attempted.at_family;
    "rejected_tactic", `String tactic_text;
    "exact_resource", `String attempted.at_resource;
    "argument_kinds", `List (List.map (fun x -> `String x)
      attempted.at_argument_kinds);
    "side", `String attempted.at_side;
    "positions", `List (List.map (fun x -> `Int x) attempted.at_positions);
    "native_diagnostic_status", `String diagnostic_status;
    "native_failure_kind", `String failure_kind;
    "native_error_message", `String message;
    "attempt_outcome", `String observed_outcome_kind;
    "goal_kind", `String (goal_kind ());
    "application_head", Option.value ~default:`Null application_head;
    "proof_term", Option.value ~default:`Null proof_descriptor;
    "relation_bridge", Option.value ~default:`Null relation_bridge;
    "relation_bridge_choice", `Null;
    "phl_transitivity_boundary", `Null;
    "eager_while_dialect", `Null;
    "pure_tail_rewrite", Option.value ~default:`Null pure_tail_rewrite;
    "intro_pattern_realization", `Null;
    "application_syntax_repair", `Null;
  ]

let attempt_diagnostic_descriptor tactic_text observed_outcome_kind =
  try
    let attempted = parse_attempted_tactic tactic_text in
    Ok (attempt_descriptor tactic_text observed_outcome_kind attempted)
  with
  | EcParsetree.ParseError (_, message) ->
      let parse_message = Option.value ~default:"parse error" message in
      begin match application_module_syntax_failure_descriptor tactic_text
          observed_outcome_kind parse_message with
      | Some descriptor -> Ok descriptor
      | None -> begin match eager_while_parse_failure_descriptor tactic_text
          observed_outcome_kind parse_message with
      | Some descriptor -> Ok descriptor
      | None -> begin match transitivity_attempt_descriptor tactic_text
          observed_outcome_kind parse_message with
      | Some descriptor -> Ok descriptor
      | None -> begin match change_parse_failure_descriptor tactic_text
            observed_outcome_kind parse_message with
          | Some descriptor -> Ok descriptor
          | None -> Error (`Assoc [
              "code", `String "parse_error";
              "message", `String parse_message;])
          end
          end
      end
      end
  | Contract_error message ->
      begin match intro_pattern_failure_descriptor tactic_text
          observed_outcome_kind with
      | Some descriptor -> Ok descriptor
      | None -> begin match eager_while_guard_failure_descriptor tactic_text
          observed_outcome_kind with
      | Some descriptor -> Ok descriptor
      | None -> begin match phl_transitivity_attempt_descriptor tactic_text
          observed_outcome_kind with
      | Some descriptor -> Ok descriptor
      | None -> Error (`Assoc [
          "code", `String "unsupported_attempt_shape";
          "message", `String message;])
      end
      end
      end

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

let tactic_prefix_diagnostic_descriptor tactic_text candidate_prefixes =
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
                match attempt_diagnostic_descriptor tactic "rejected" with
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

let typed_selected_bindings selected_resource module_candidates head =
  let maximum_typed_bindings = 64 in
  let maximum_candidate_checks = 4096 in
  let overflow = ref false in
  let candidate_checks = ref 0 in
  let completed = ref [] in
  let rec visit (branch : selected_binding_branch) =
    if !overflow then () else
    match EcProofTyping.destruct_product ~reduce:false
        branch.sbb_replay.ptev_env.pte_hy branch.sbb_replay.ptev_ax with
    | None ->
        completed := branch :: !completed;
        if List.length !completed > maximum_typed_bindings then
          overflow := true
    | Some (`Imp _) ->
        let replay = EcProofTerm.apply_pterm_to_hole branch.sbb_replay in
        visit { sbb_replay = replay;
          sbb_arguments_rev = "_" :: branch.sbb_arguments_rev; }
    | Some (`Forall (_, GTmodty _, _)) ->
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
  let checked = if overflow then [] else List.filter_map
    (checked_selected_application operation selected_resource)
    typed_bindings in
  let checked = List.sort_uniq (fun left right ->
    String.compare
      (json_string "application_term" left)
      (json_string "application_term" right)) checked in
  let checked_count = List.length checked in
  let ppe = EcPrinting.PPEnv.ofenv
    (EcScope.env (EcCommands.current ())) in
  let resolved = resolved_head head.ptev_pt in
  let complete = not overflow in
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
      else "");
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
  end else if query_kind = "tactic_prefix_diagnostic" then begin
    let tactic_text = json_string "rejected_tactic" payload in
    let candidate_prefixes = json_string_list "candidate_prefixes" payload in
    try
      let descriptor = tactic_prefix_diagnostic_descriptor
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
    match attempt_diagnostic_descriptor tactic_text observed_outcome_kind with
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

let run request =
  if request |> member "schema_version" |> to_int <> 17 then
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
  initialize include_dirs;
  process_file context_file;
  process_file history_file;
  let goal = goal_text () in
  `Assoc [
    "schema_version", `Int 17;
    "kind", `String "native_semantic_batch_result";
    "batch_id", `String batch_id;
    "goal_before", `String goal;
    "results", `List (List.map run_query requests);
  ]

let () =
  let response =
    try run (Yojson.Safe.from_channel stdin) with
    | Contract_error message -> `Assoc [
      "schema_version", `Int 17;
        "kind", `String "native_semantic_batch_result";
        "status", `String "contract_error";
        "message", `String message;
      ]
    | exn -> `Assoc [
      "schema_version", `Int 17;
        "kind", `String "native_semantic_batch_result";
        "status", `String "adapter_error";
        "message", `String (Printexc.to_string exn);
      ]
  in
  output_string stdout "SHANNON_NATIVE_SEMANTIC_V1:";
  Yojson.Safe.to_channel stdout response;
  output_char stdout '\n';
  flush stdout
