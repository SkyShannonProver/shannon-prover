(* Read-only typed proof-state projection over the replayed EasyCrypt tcenv1. *)

open EcLib
open EcAst
open EcFol
open EcBaseLogic
open Yojson.Safe.Util
open Native_adapter_common

type budget = {
  max_nodes : int;
  max_depth : int;
  mutable node_count : int;
  mutable truncation_reasons : string list;
}

let add_reason budget reason =
  if not (List.mem reason budget.truncation_reasons) then
    budget.truncation_reasons <- reason :: budget.truncation_reasons

let reserve budget depth =
  if depth > budget.max_depth then begin
    add_reason budget "max_depth";
    false
  end else if budget.node_count >= budget.max_nodes then begin
    add_reason budget "max_nodes";
    false
  end else begin
    budget.node_count <- budget.node_count + 1;
    true
  end

let truncated_node reason =
  `Assoc [
    "kind", `String "truncated";
    "complete", `Bool false;
    "reason", `String reason;
  ]

let pp printer value = Format.asprintf "%a" printer value

let project_stage name action =
  try action () with exn ->
    raise (Contract_error (
      "native state projection " ^ name ^ " failed: " ^
      exception_text exn))

let memory_text memory = EcIdent.name memory

let quantifier_text = function
  | Lforall -> "forall"
  | Lexists -> "exists"
  | Llambda -> "lambda"

let expression_quantifier_text = function
  | `ELambda -> "lambda"
  | `EForall -> "forall"
  | `EExists -> "exists"

let path_json path = `List (List.map (fun item -> `String item) path)

let string_list_json values =
  `List (List.map (fun value -> `String value) values)

let xpath_set_json values =
  values
  |> EcPath.Sx.elements
  |> List.map (fun value -> `String (EcPath.x_tostring value))
  |> fun values -> `List values

let mpath_set_json values =
  values
  |> EcPath.Sm.elements
  |> List.map (fun value -> `String (EcPath.m_tostring value))
  |> fun values -> `List values

let exception_path_text = function
  | None -> "<default>"
  | Some path -> EcPath.tostring path

let exception_path_json = function
  | None -> `Null
  | Some path -> `String (EcPath.tostring path)

let restriction_part_json (xpaths, mpaths) =
  `Assoc [
    "procedures", xpath_set_json xpaths;
    "modules", mpath_set_json mpaths;
  ]

let restriction_json restriction =
  `Assoc [
    "positive", begin match restriction.ur_pos with
      | None -> `Null
      | Some value -> restriction_part_json value
    end;
    "negative", restriction_part_json restriction.ur_neg;
  ]

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

let generic_type_json ppe = function
  | GTty ty -> `Assoc [
      "kind", `String "type";
      "text", `String (type_text ppe ty);
    ]
  | GTmodty (module_type, restriction) -> `Assoc [
      "kind", `String "module";
      "text", `String (pp (EcPrinting.pp_modtype1 ppe) module_type);
      "restriction", restriction_json restriction;
    ]
  | GTmem memory_type -> `Assoc [
      "kind", `String "memory";
      "text", `String (pp (EcPrinting.pp_memtype ppe) memory_type);
    ]

let program_variable_json ppe variable ty =
  let kind, identity = match variable with
    | PVglob xpath -> "global", EcPath.x_tostring xpath
    | PVloc name -> "local", name
  in
  `Assoc [
    "kind", `String kind;
    "identity", `String identity;
    "display", `String (pp (EcPrinting.pp_pv ppe) variable);
    "type", `String (type_text ppe ty);
  ]

let lvalue_json ppe = function
  | LvVar (variable, ty) -> `Assoc [
      "kind", `String "variable";
      "variables", `List [program_variable_json ppe variable ty];
    ]
  | LvTuple variables -> `Assoc [
      "kind", `String "tuple";
      "variables", `List (List.map
        (fun (variable, ty) -> program_variable_json ppe variable ty)
        variables);
    ]

let pattern_json ppe = function
  | LSymbol (identifier, ty) -> `Assoc [
      "kind", `String "symbol";
      "bindings", `List [`Assoc [
        "name", `String (EcIdent.name identifier);
        "type", `String (type_text ppe ty);
      ]];
    ]
  | LTuple bindings -> `Assoc [
      "kind", `String "tuple";
      "bindings", `List (List.map (fun (identifier, ty) -> `Assoc [
        "name", `String (EcIdent.name identifier);
        "type", `String (type_text ppe ty);
      ]) bindings);
    ]
  | LRecord (record_path, bindings) -> `Assoc [
      "kind", `String "record";
      "record_path", `String (EcPath.tostring record_path);
      "bindings", `List (List.map (fun (identifier, ty) -> `Assoc [
        "name", begin match identifier with
          | None -> `Null
          | Some value -> `String (EcIdent.name value)
        end;
        "type", `String (type_text ppe ty);
      ]) bindings);
    ]

let rec expression_json budget ppe depth expression =
  if not (reserve budget depth) then truncated_node "expression_budget"
  else
    let base kind fields children = `Assoc (
      ("kind", `String kind) ::
      ("complete", `Bool true) ::
      ("text", `String (pp (EcPrinting.pp_expr ppe) expression)) ::
      ("type", `String (type_text ppe expression.e_ty)) ::
      ("children", `List children) :: fields)
    in
    match expression.e_node with
    | Eint _ -> base "integer" [] []
    | Elocal identifier -> base "local" [
        "name", `String (EcIdent.name identifier)
      ] []
    | Evar variable ->
        let identity = match variable with
          | PVglob xpath -> EcPath.x_tostring xpath
          | PVloc name -> name
        in
        base "program_variable" ["identity", `String identity] []
    | Eop (path, types) -> base "operator" [
        "operator", `String (EcPath.tostring path);
        "type_arguments", `List (List.map
          (fun ty -> `String (type_text ppe ty)) types);
      ] []
    | Eapp (head, arguments) -> base "application" []
        (List.map (expression_json budget ppe (depth + 1))
          (head :: arguments))
    | Equant (quantifier, bindings, body) -> base "quantifier" [
        "quantifier", `String (expression_quantifier_text quantifier);
        "bindings", `List (List.map (fun (identifier, ty) -> `Assoc [
          "name", `String (EcIdent.name identifier);
          "type", `String (type_text ppe ty);
        ]) bindings);
      ] [expression_json budget ppe (depth + 1) body]
    | Elet (pattern, value, body) -> base "let" [
        "pattern", pattern_json ppe pattern;
      ] [
        expression_json budget ppe (depth + 1) value;
        expression_json budget ppe (depth + 1) body;
      ]
    | Etuple values -> base "tuple" []
        (List.map (expression_json budget ppe (depth + 1)) values)
    | Eif (condition, when_true, when_false) -> base "if" [] [
        expression_json budget ppe (depth + 1) condition;
        expression_json budget ppe (depth + 1) when_true;
        expression_json budget ppe (depth + 1) when_false;
      ]
    | Ematch (scrutinee, branches, result_type) -> base "match" [
        "result_type", `String (type_text ppe result_type);
      ] (List.map (expression_json budget ppe (depth + 1))
        (scrutinee :: branches))
    | Eproj (value, index) -> base "projection" [
        "index", `Int index;
      ] [expression_json budget ppe (depth + 1) value]

let rec formula_json budget ppe depth formula =
  if not (reserve budget depth) then truncated_node "formula_budget"
  else
    let base kind fields children = `Assoc (
      ("kind", `String kind) ::
      ("complete", `Bool true) ::
      ("text", `String (pp (EcPrinting.pp_form ppe) formula)) ::
      ("type", `String (type_text ppe formula.f_ty)) ::
      ("children", `List children) :: fields)
    in
    let children values =
      List.map (formula_json budget ppe (depth + 1)) values
    in
    match EcFol.sform_of_form formula with
    | SFint _ -> base "integer" [] []
    | SFlocal identifier -> base "local" [
        "name", `String (EcIdent.name identifier)
      ] []
    | SFpvar (variable, memory) ->
        let identity = match variable with
          | PVglob xpath -> EcPath.x_tostring xpath
          | PVloc name -> name
        in
        base "program_variable" [
          "identity", `String identity;
          "memory", `String (memory_text memory);
        ] []
    | SFglob (identifier, memory) -> base "module_global" [
        "module", `String (EcIdent.name identifier);
        "memory", `String (memory_text memory);
      ] []
    | SFif (condition, when_true, when_false) ->
        base "if" [] (children [condition; when_true; when_false])
    | SFmatch (scrutinee, branches, result_type) -> base "match" [
        "result_type", `String (type_text ppe result_type);
      ] (children (scrutinee :: branches))
    | SFlet (pattern, value, body) -> base "let" [
        "pattern", pattern_json ppe pattern;
      ] (children [value; body])
    | SFtuple values -> base "tuple" [] (children values)
    | SFproj (value, index) -> base "projection" [
        "index", `Int index;
      ] (children [value])
    | SFquant (quantifier, (identifier, generic_type), body) ->
        base "quantifier" [
          "quantifier", `String (quantifier_text quantifier);
          "binding", `Assoc [
            "name", `String (EcIdent.name identifier);
            "generic_type", generic_type_json ppe generic_type;
          ];
        ] (children [Lazy.force body])
    | SFtrue -> base "true" [] []
    | SFfalse -> base "false" [] []
    | SFnot value -> base "not" [] (children [value])
    | SFand (symmetry, (left, right)) -> base "and" [
        "evaluation", `String (match symmetry with
          | `Asym -> "asymmetric" | `Sym -> "symmetric");
      ] (children [left; right])
    | SFor (symmetry, (left, right)) -> base "or" [
        "evaluation", `String (match symmetry with
          | `Asym -> "asymmetric" | `Sym -> "symmetric");
      ] (children [left; right])
    | SFimp (premise, conclusion) ->
        base "implication" [] (children [premise; conclusion])
    | SFiff (left, right) -> base "iff" [] (children [left; right])
    | SFeq (left, right) -> base "equality" [] (children [left; right])
    | SFop ((path, types), arguments) ->
        let relation = match relation_operator path with
          | None -> []
          | Some value -> ["relation_operator", `String value]
        in
        base "operator_application" (
          ("operator", `String (EcPath.tostring path)) ::
          ("type_arguments", `List (List.map
            (fun ty -> `String (type_text ppe ty)) types)) :: relation
        ) (children arguments)
    | SFhoareF judgment -> base "hoare_function" [
        "memory", `String (memory_text judgment.hf_m);
        "procedure", `String (EcPath.x_tostring judgment.hf_f);
        "child_roles", string_list_json ["precondition"; "postcondition"];
      ] [
        formula_json budget ppe (depth + 1) (hf_pr judgment).inv;
        exceptional_postcondition_json budget ppe (depth + 1)
          (hf_po judgment).hsi_inv;
      ]
    | SFhoareS judgment -> base "hoare_statement" [
        "memory", `String (memory_text (fst judgment.hs_m));
        "child_roles", string_list_json ["precondition"; "postcondition"];
      ] [
        formula_json budget ppe (depth + 1) (hs_pr judgment).inv;
        exceptional_postcondition_json budget ppe (depth + 1)
          (hs_po judgment).hsi_inv;
      ]
    | SFbdHoareF judgment -> base "bounded_hoare_function" [
        "memory", `String (memory_text judgment.bhf_m);
        "procedure", `String (EcPath.x_tostring judgment.bhf_f);
        "comparison", `String (EcPrinting.string_of_hcmp judgment.bhf_cmp);
        "lossless", `Bool (
             EcFol.f_equal EcFol.f_true (bhf_pr judgment).inv
          && EcFol.f_equal EcFol.f_true (bhf_po judgment).inv
          && EcFol.f_equal EcFol.f_r1 (bhf_bd judgment).inv
          && judgment.bhf_cmp = FHeq);
        "child_roles", string_list_json
          ["precondition"; "postcondition"; "bound"];
      ] (children [
        (bhf_pr judgment).inv;
        (bhf_po judgment).inv;
        (bhf_bd judgment).inv;
      ])
    | SFbdHoareS judgment -> base "bounded_hoare_statement" [
        "memory", `String (memory_text (fst judgment.bhs_m));
        "comparison", `String (EcPrinting.string_of_hcmp judgment.bhs_cmp);
        "child_roles", string_list_json
          ["precondition"; "postcondition"; "bound"];
      ] (children [
        (bhs_pr judgment).inv;
        (bhs_po judgment).inv;
        (bhs_bd judgment).inv;
      ])
    | SFequivF judgment -> base "equivalence_function" [
        "left_memory", `String (memory_text judgment.ef_ml);
        "right_memory", `String (memory_text judgment.ef_mr);
        "left_procedure", `String (EcPath.x_tostring judgment.ef_fl);
        "right_procedure", `String (EcPath.x_tostring judgment.ef_fr);
        "child_roles", string_list_json ["precondition"; "postcondition"];
      ] (children [(ef_pr judgment).inv; (ef_po judgment).inv])
    | SFequivS judgment -> base "equivalence_statement" [
        "left_memory", `String (memory_text (fst judgment.es_ml));
        "right_memory", `String (memory_text (fst judgment.es_mr));
        "child_roles", string_list_json ["precondition"; "postcondition"];
      ] (children [(es_pr judgment).inv; (es_po judgment).inv])
    | SFpr probability -> base "probability" [
        "memory", `String (memory_text probability.pr_mem);
        "procedure", `String (EcPath.x_tostring probability.pr_fun);
        "procedure_module", module_path_json ppe probability.pr_fun.EcPath.x_top;
        "child_roles", string_list_json ["arguments"; "event"];
      ] (children [probability.pr_args; probability.pr_event.inv])
    | SFother other -> begin match other.f_node with
        | FeHoareF judgment -> base "expectation_hoare_function" [
            "memory", `String (memory_text judgment.ehf_m);
            "procedure", `String (EcPath.x_tostring judgment.ehf_f);
            "child_roles", string_list_json
              ["precondition"; "postcondition"];
          ] (children [(ehf_pr judgment).inv; (ehf_po judgment).inv])
        | FeHoareS judgment -> base "expectation_hoare_statement" [
            "memory", `String (memory_text (fst judgment.ehs_m));
            "child_roles", string_list_json
              ["precondition"; "postcondition"];
          ] (children [(ehs_pr judgment).inv; (ehs_po judgment).inv])
        | FeagerF judgment -> base "eager_equivalence" [
            "left_memory", `String (memory_text judgment.eg_ml);
            "right_memory", `String (memory_text judgment.eg_mr);
            "left_procedure", `String (EcPath.x_tostring judgment.eg_fl);
            "right_procedure", `String (EcPath.x_tostring judgment.eg_fr);
            "child_roles", string_list_json
              ["precondition"; "postcondition"];
          ] (children [(eg_pr judgment).inv; (eg_po judgment).inv])
        | Fapp (head, arguments) ->
            base "application" [] (children (head :: arguments))
        | Fop (path, types) -> base "operator" [
            "operator", `String (EcPath.tostring path);
            "type_arguments", `List (List.map
              (fun ty -> `String (type_text ppe ty)) types);
          ] []
        | _ ->
            add_reason budget "unsupported_formula_node";
            `Assoc [
              "kind", `String "other";
              "complete", `Bool false;
              "text", `String (pp (EcPrinting.pp_form ppe) other);
              "type", `String (type_text ppe other.f_ty);
              "children", `List [];
            ]
      end

and exceptional_postcondition_json budget ppe depth postcondition =
  if not (reserve budget depth) then
    truncated_node "exceptional_postcondition_budget"
  else
    let exceptions = EcPath.Mop.bindings postcondition.exnmap in
    let exception_texts =
      List.map (fun (path, formula) ->
        Printf.sprintf "exception %s => %s"
          (exception_path_text path)
          (pp (EcPrinting.pp_form ppe) formula))
        exceptions
    in
    let text = String.concat "; " (
      ("normal => " ^ pp (EcPrinting.pp_form ppe) postcondition.main) ::
      exception_texts)
    in
    let children =
      formula_json budget ppe (depth + 1) postcondition.main ::
      List.map (fun (_, formula) ->
        formula_json budget ppe (depth + 1) formula)
        exceptions
    in
    `Assoc [
      "kind", `String "exceptional_postcondition";
      "complete", `Bool true;
      "text", `String text;
      "type", `String (type_text ppe postcondition.main.f_ty);
      "children", `List children;
      "child_roles", string_list_json (
        "normal_postcondition" ::
        List.map (fun _ -> "exception_postcondition") exceptions);
      "exception_paths", `List (
        List.map (fun (path, _) -> exception_path_json path) exceptions);
    ]

let rec statement_json budget ppe depth path top_level statement =
  if not (reserve budget depth) then truncated_node "statement_budget"
  else
    let instructions = List.mapi (fun index instruction ->
      let position = index + 1 in
      instruction_json budget ppe (depth + 1)
        (path @ [string_of_int position])
        (if top_level then Some position else None)
        instruction)
      statement.s_node
    in
    `Assoc [
      "kind", `String "statement";
      "complete", `Bool true;
      "structural_path", path_json path;
      "text", `String (pp (EcPrinting.pp_stmt ~lineno:false ppe) statement);
      "instructions", `List instructions;
    ]

and instruction_json budget ppe depth path top_level_position instruction =
  if not (reserve budget depth) then truncated_node "instruction_budget"
  else
    let base kind fields = `Assoc (
      ("kind", `String kind) ::
      ("complete", `Bool true) ::
      ("structural_path", path_json path) ::
      ("top_level_position", begin match top_level_position with
        | None -> `Null | Some value -> `Int value
      end) ::
      ("text", `String (pp (EcPrinting.pp_instr ppe) instruction)) :: fields)
    in
    match instruction.i_node with
    | Sasgn (target, value) -> base "assign" [
        "target", lvalue_json ppe target;
        "value", expression_json budget ppe (depth + 1) value;
      ]
    | Srnd (target, distribution) -> base "sample" [
        "target", lvalue_json ppe target;
        "distribution", expression_json budget ppe (depth + 1) distribution;
      ]
    | Scall (target, procedure, arguments) -> base "call" [
        "target", begin match target with
          | None -> `Null | Some value -> lvalue_json ppe value
        end;
        "procedure", `String (EcPath.x_tostring procedure);
        "arguments", `List (List.map
          (expression_json budget ppe (depth + 1)) arguments);
      ]
    | Sif (condition, when_true, when_false) -> base "if" [
        "condition", expression_json budget ppe (depth + 1) condition;
        "then_statement", statement_json budget ppe (depth + 1)
          (path @ ["then"]) false when_true;
        "else_statement", statement_json budget ppe (depth + 1)
          (path @ ["else"]) false when_false;
      ]
    | Swhile (condition, body) -> base "while" [
        "condition", expression_json budget ppe (depth + 1) condition;
        "body", statement_json budget ppe (depth + 1)
          (path @ ["body"]) false body;
      ]
    | Smatch (scrutinee, branches) -> base "match" [
        "scrutinee", expression_json budget ppe (depth + 1) scrutinee;
        "branches", `List (List.mapi (fun index (bindings, body) -> `Assoc [
          "index", `Int index;
          "bindings", `List (List.map (fun (identifier, ty) -> `Assoc [
            "name", `String (EcIdent.name identifier);
            "type", `String (type_text ppe ty);
          ]) bindings);
          "body", statement_json budget ppe (depth + 1)
            (path @ ["branch"; string_of_int index]) false body;
        ]) branches);
      ]
    | Sraise exception_value -> base "raise" [
        "exception", expression_json budget ppe (depth + 1) exception_value;
      ]
    | Sabstract identifier -> base "abstract" [
        "identifier", `String (EcIdent.name identifier);
      ]

let program_json budget ppe side role memory statement =
  `Assoc [
    "side", `String side;
    "role", `String role;
    "memory", `String (memory_text memory);
    "statement", statement_json budget ppe 0 [side] true statement;
  ]

let uses_json ppe uses =
  let variables values = `List (List.map (fun (variable, ty) ->
    program_variable_json ppe variable ty) values)
  in
  `Assoc [
    "calls", string_list_json
      (List.map EcPath.x_tostring uses.EcModules.aus_calls);
    "reads", variables uses.EcModules.aus_reads;
    "writes", variables uses.EcModules.aus_writes;
  ]

let local_declaration_json budget ppe index (identifier, local_kind) =
  let base kind fields = `Assoc (
    ("index", `Int index) ::
    ("name", `String (EcIdent.name identifier)) ::
    ("kind", `String kind) :: fields)
  in
  match local_kind with
  | LD_var (ty, definition) -> base "variable" [
      "type", `String (type_text ppe ty);
      "definition", begin match definition with
        | None -> `Null
        | Some value -> formula_json budget ppe 0 value
      end;
    ]
  | LD_mem memory_type -> base "memory" [
      "memory_type", `String (pp (EcPrinting.pp_memtype ppe) memory_type);
    ]
  | LD_modty (module_type, restriction) -> base "module" [
      "module_type", `String (pp (EcPrinting.pp_modtype1 ppe) module_type);
      "restriction", restriction_json restriction;
    ]
  | LD_hyp formula -> base "hypothesis" [
      "formula", formula_json budget ppe 0 formula;
    ]
  | LD_abs_st uses -> base "abstract_statement" [
      "uses", uses_json ppe uses;
    ]

let judgment_kind formula = match formula.f_node with
  | FhoareF _ -> "hoare_function"
  | FhoareS _ -> "hoare_statement"
  | FbdHoareF _ -> "bounded_hoare_function"
  | FbdHoareS _ -> "bounded_hoare_statement"
  | FeHoareF _ -> "expectation_hoare_function"
  | FeHoareS _ -> "expectation_hoare_statement"
  | FequivF _ -> "equivalence_function"
  | FequivS _ -> "equivalence_statement"
  | FeagerF _ -> "eager_equivalence"
  | Fpr _ -> "probability"
  | _ -> "pure"

let programs_json budget ppe formula =
  let programs = match formula.f_node with
    | FhoareS judgment -> [
        program_json budget ppe "single" "body"
          (fst judgment.hs_m) judgment.hs_s
      ]
    | FbdHoareS judgment -> [
        program_json budget ppe "single" "body"
          (fst judgment.bhs_m) judgment.bhs_s
      ]
    | FeHoareS judgment -> [
        program_json budget ppe "single" "body"
          (fst judgment.ehs_m) judgment.ehs_s
      ]
    | FequivS judgment -> [
        program_json budget ppe "left" "left_body"
          (fst judgment.es_ml) judgment.es_sl;
        program_json budget ppe "right" "right_body"
          (fst judgment.es_mr) judgment.es_sr;
      ]
    | FeagerF judgment -> [
        program_json budget ppe "left" "left_prefix"
          judgment.eg_ml judgment.eg_sl;
        program_json budget ppe "right" "right_suffix"
          judgment.eg_mr judgment.eg_sr;
      ]
    | _ -> []
  in
  `List programs

let procedures_json ppe formula =
  let procedure side role xpath = `Assoc [
    "side", `String side;
    "role", `String role;
    "procedure", `String (EcPath.x_tostring xpath);
    "procedure_module", module_path_json ppe xpath.EcPath.x_top;
  ]
  in
  let procedures = match formula.f_node with
    | FhoareF judgment -> [procedure "single" "subject" judgment.hf_f]
    | FbdHoareF judgment -> [procedure "single" "subject" judgment.bhf_f]
    | FeHoareF judgment -> [procedure "single" "subject" judgment.ehf_f]
    | FequivF judgment -> [
        procedure "left" "left_subject" judgment.ef_fl;
        procedure "right" "right_subject" judgment.ef_fr;
      ]
    | FeagerF judgment -> [
        procedure "left" "left_subject" judgment.eg_fl;
        procedure "right" "right_subject" judgment.eg_fr;
      ]
    | Fpr probability -> [
        procedure "single" "probability_subject" probability.pr_fun
      ]
    | _ -> []
  in
  `List procedures

let project max_nodes max_depth =
  let proof = project_stage "current proof" current_proof in
  let opened = project_stage "opened goals" (fun () ->
    EcCoreGoal.all_opened proof)
  in
  if opened = [] then
    raise (Contract_error "native state requires one open goal");
  (* EasyCrypt owns focus through tcenv1_of_proof.  all_opened is used only
     for cardinality; its list order is not a focus contract. *)
  let focused = project_stage "focused goal" (fun () ->
    EcCoreGoal.tcenv1_of_proof proof)
  in
  let hypotheses = project_stage "focused hypotheses" (fun () ->
    EcCoreGoal.FApi.tc1_hyps focused)
  in
  let goal = project_stage "focused conclusion" (fun () ->
    EcCoreGoal.FApi.tc1_goal focused)
  in
  let environment = project_stage "local environment" (fun () ->
    EcEnv.LDecl.toenv hypotheses)
  in
  let ppe = project_stage "printing environment" (fun () ->
    EcPrinting.PPEnv.ofenv environment)
  in
  let budget = {
    max_nodes;
    max_depth;
    node_count = 0;
    truncation_reasons = [];
  } in
  let locals = project_stage "local context" (fun () ->
    (EcEnv.LDecl.tohyps hypotheses).h_local)
  in
  let local_declarations = project_stage "local declarations" (fun () ->
    List.mapi (local_declaration_json budget ppe) locals)
  in
  let formula = project_stage "focused formula" (fun () ->
    formula_json budget ppe 0 goal)
  in
  let programs = project_stage "focused programs" (fun () ->
    programs_json budget ppe goal)
  in
  let procedures = project_stage "focused procedures" (fun () ->
    procedures_json ppe goal)
  in
  let complete = budget.truncation_reasons = [] in
  `Assoc [
    "complete", `Bool complete;
    "truncation_reasons", string_list_json
      (List.rev budget.truncation_reasons);
    "node_count", `Int budget.node_count;
    "open_goal_count", `Int (List.length opened);
    "focused_goal", `Assoc [
      "judgment_kind", `String (judgment_kind goal);
      "formula", formula;
      "programs", programs;
      "procedures", procedures;
    ];
    "local_declarations", `List local_declarations;
  ]

let response_base request_id goal max_nodes max_depth = [
  "schema_version", `Int 2;
  "kind", `String "native_proof_state_projection_result";
  "request_id", `String request_id;
  "goal_before", `String goal;
  "limits", `Assoc [
    "max_nodes", `Int max_nodes;
    "max_depth", `Int max_depth;
  ];
]

let run request =
  if request |> member "schema_version" |> to_int <> 2 then
    raise (Contract_error "unsupported request schema_version");
  if request |> member "kind" |> to_string <>
      "native_proof_state_projection_request" then
    raise (Contract_error "unsupported request kind");
  let request_id = json_string "request_id" request in
  let context_file = json_string "context_file" request in
  let history_file = json_string "history_file" request in
  let include_dirs = json_string_list "include_dirs" request in
  let max_nodes = json_int "max_nodes" request in
  let max_depth = json_int "max_depth" request in
  if max_nodes < 64 || max_nodes > 100000 then
    raise (Contract_error "max_nodes is outside the supported range");
  if max_depth < 8 || max_depth > 512 then
    raise (Contract_error "max_depth is outside the supported range");
  initialize include_dirs;
  project_stage "context replay" (fun () -> process_file context_file);
  project_stage "history replay" (fun () -> process_file history_file);
  let goal = project_stage "goal rendering" goal_text in
  let base = response_base request_id goal max_nodes max_depth in
  `Assoc (("status", `String "accepted") ::
    ("projection", project max_nodes max_depth) :: base)

let () =
  let response =
    try run (Yojson.Safe.from_channel stdin) with
    | Contract_error message -> `Assoc [
        "schema_version", `Int 2;
        "kind", `String "native_proof_state_projection_result";
        "status", `String "contract_error";
        "message", `String message;
      ]
    | EcParsetree.ParseError (_, message) -> `Assoc [
        "schema_version", `Int 2;
        "kind", `String "native_proof_state_projection_result";
        "status", `String "adapter_error";
        "message", `String (Option.value ~default:"parse error" message);
      ]
    | exn -> `Assoc [
        "schema_version", `Int 2;
        "kind", `String "native_proof_state_projection_result";
        "status", `String "adapter_error";
        "message", `String (Printexc.to_string exn);
      ]
  in
  output_string stdout "SHANNON_NATIVE_STATE_V1:";
  Yojson.Safe.to_channel stdout response;
  output_char stdout '\n';
  flush stdout
