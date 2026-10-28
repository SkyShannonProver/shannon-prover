(* relation_bridge_realization: an agent-written intermediate for a real or
   integer relation goal, written as [transitivity t.] or as a [change] whose
   target is not convertible to the goal.  [bridge] realizes one certificate
   for non-strict goals; [choice] lists the three certificates of a strict
   real goal.  The two read disjoint goal shapes. *)

open EcLib
open EcAst
open EcFol
open Native_semantic_support

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
  let globals = parse_sentences tactic_text in
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

let bridge_payload source_operation relation_family certificate_family
    intermediate intermediate_type source_target_present target_convertible
    target_right_convertible =
  let candidate = "apply (" ^ certificate_family ^ " " ^ intermediate
    ^ "); first last." in
  `Assoc [
    "source_operation", `String source_operation;
    "relation_family", `String relation_family;
    "intermediate_text", `String intermediate;
    "intermediate_type", `String intermediate_type;
    "candidate_tactic", `String candidate;
    "source_target_present", `Bool source_target_present;
    "source_target_convertible_to_current_goal", `Bool target_convertible;
    "source_target_right_convertible_to_current_right",
      `Bool target_right_convertible;
  ]

let formula_core family error_message = Some {
  Realizer.family;
  resource = "";
  argument_kinds = ["formula"];
  side = "";
  error_message;
  application_head = `Null;
}

let one_argument prefix tactic_text =
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

(* The written intermediate [argument] typed as the left side of the goal's
   relation, provided its right side is convertible to the goal's. *)
let typed_intermediate tc relation_text view argument current_right =
  let ppe = EcPrinting.PPEnv.ofenv (EcScope.env (EcCommands.current ())) in
  let probe = "change (" ^ argument ^ " " ^ relation_text ^ " "
    ^ (pp (EcPrinting.pp_form ppe) current_right) ^ ")." in
  let target = EcProofTyping.tc1_process_formula tc (parse_change_target probe) in
  match view target with
  | None -> None
  | Some (intermediate, target_right) ->
      let hyps = EcCoreGoal.FApi.tc1_hyps tc in
      if EcReduction.is_conv ~ri:EcReduction.full_compat
          hyps target_right current_right
      then Some (ppe, intermediate)
      else None

(* A change target that is not convertible to a non-strict real goal but
   shares its right side bridges the goal through the target's left side. *)
let change_bridge tc parsed error_message =
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
      let ppe = EcPrinting.PPEnv.ofenv (EcScope.env (EcCommands.current ())) in
      Some {
        Realizer.failure_kind = "change_target_not_convertible";
        core = Option.bind error_message (formula_core "change");
        payload = bridge_payload "change" "real_le" "ler_trans"
          (pp (EcPrinting.pp_form ppe) intermediate)
          (type_text ppe intermediate.f_ty)
          true false true;
      }
  | _ -> None

let transitivity_bridge tactic parse_message =
  match one_argument "transitivity " tactic with
  | None -> None
  | Some argument ->
      let tc = current_tcenv1 () in
      let goal = EcCoreGoal.FApi.tc1_goal tc in
      let bridge relation_family certificate_family intermediate ppe =
        Some {
          Realizer.failure_kind = "formula_transitivity_surface_mismatch";
          core = formula_core "transitivity" parse_message;
          payload = bridge_payload "transitivity" relation_family
            certificate_family argument (type_text ppe intermediate.f_ty)
            false false false;
        }
      in
      match real_le_view goal, real_lt_view goal, int_le_view goal with
      | Some (_, current_right), None, None ->
          Option.bind (typed_intermediate tc "<=" real_le_view argument
              current_right)
            (fun (ppe, intermediate) ->
              bridge "real_le" "ler_trans" intermediate ppe)
      | None, None, Some (_, current_right) ->
          Option.bind (typed_intermediate tc "<=" int_le_view argument
              current_right)
            (fun (ppe, intermediate) ->
              bridge "int_le" "Int.lez_trans" intermediate ppe)
      | _ -> None

let bridge ~tactic = function
  | Realizer.Parsed attempted -> begin
      match attempted.at_change_formula with
      | None -> None
      | Some parsed -> begin
          try change_bridge (current_tcenv1 ()) parsed None with
          | EcCoreGoal.TcError _
          | EcTyping.TyError _
          | EcEnv.LookupFailure _ -> None
        end
    end
  | Realizer.Parse_error parse_message -> begin
      try
        match transitivity_bridge tactic parse_message with
        | Some claim -> Some claim
        | None -> begin match one_argument "change " tactic with
            | None -> None
            | Some target ->
                change_bridge (current_tcenv1 ())
                  (parse_change_target ("change (" ^ target ^ ")."))
                  (Some parse_message)
          end
      with
      | EcParsetree.ParseError _
      | EcCoreGoal.TcError _
      | EcTyping.TyError _
      | EcEnv.LookupFailure _
      | Contract_error _ -> None
    end
  | Realizer.Unsupported_shape _ -> None

let choice ~tactic = function
  | Realizer.Parse_error parse_message -> begin
      match one_argument "transitivity " tactic with
      | None -> None
      | Some argument -> begin
          try
            let tc = current_tcenv1 () in
            match real_lt_view (EcCoreGoal.FApi.tc1_goal tc) with
            | None -> None
            | Some (current_left, current_right) ->
                Option.map (fun (ppe, intermediate) ->
                  let choices = List.map
                    (fun (family, left_relation, right_relation) ->
                      let candidate = "apply (" ^ family ^ " " ^ argument
                        ^ "); first last." in
                      if not (native_preflight_candidate candidate) then
                        raise (Contract_error
                          "strict relation bridge candidate did not preflight");
                      `Assoc [
                        "certificate_family", `String family;
                        "left_relation", `String left_relation;
                        "right_relation", `String right_relation;
                        "candidate_tactic", `String candidate;
                      ])
                    [ ("ler_lt_trans", "<=", "<");
                      ("ltr_le_trans", "<", "<=");
                      ("ltr_trans", "<", "<") ] in
                  {
                    Realizer.failure_kind =
                      "formula_transitivity_surface_mismatch";
                    core = formula_core "transitivity" parse_message;
                    payload = `Assoc [
                      "source_operation", `String "transitivity";
                      "relation_family", `String "real_lt";
                      "goal_left_text",
                        `String (pp (EcPrinting.pp_form ppe) current_left);
                      "intermediate_text", `String argument;
                      "goal_right_text",
                        `String (pp (EcPrinting.pp_form ppe) current_right);
                      "intermediate_type",
                        `String (type_text ppe intermediate.f_ty);
                      "choices", `List choices;
                    ];
                  })
                  (typed_intermediate tc "<" real_lt_view argument
                    current_right)
          with
          | EcParsetree.ParseError _
          | EcCoreGoal.TcError _
          | EcTyping.TyError _
          | EcEnv.LookupFailure _
          | Contract_error _ -> None
        end
    end
  | Realizer.Parsed _ | Realizer.Unsupported_shape _ -> None

let realizers = [
  { Realizer.kind = "relation_bridge_realization.bridge"; realize = bridge };
  { Realizer.kind = "relation_bridge_realization.choice"; realize = choice };
]
