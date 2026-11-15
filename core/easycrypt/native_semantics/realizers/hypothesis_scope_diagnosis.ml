(* hypothesis_scope_diagnosis: a name the agent wrote in a rejected operation
   is a hypothesis of the goal, but the operation looks names up somewhere
   that hypothesis is not.

   Two lookups exclude goal hypotheses:

   - an [smt(h1 ... hn)] hint is looked up among global lemmas, axioms and
     theories only ([EcScope.Prover.process_dbhint]: [EcEnv.Ax.lookup_opt]),
     while every goal hypothesis is given to the provers anyway; and
   - [rewrite r1 ... rn in H] elaborates each rewrite proof term in the
     context before [H] ([FApi.tc1_hyps ?target] is [LDecl.local_hyps H]).

   EasyCrypt alone names the failing reference: for [smt] the location of its
   lookup error is exactly one hint, and that hint is the first one, in
   EasyCrypt's processing order, that does not resolve; for [rewrite ... in
   H] every proper prefix of the rewrite items is executed and the first
   rejected prefix names the item.  The error text is never read.

   The operation may be the whole tactic or the body of a closing [by],
   which runs that body first: when the body is rejected, [by] fails with
   the body's error.

   The claim reports native facts only.  For a bare [smt] it may also carry
   one candidate: the same tactic with exactly that hint removed, parsed back
   to the same hint list minus that hint, and accepted with progress in the
   same proof. *)

open EcLib
open Native_semantic_support

(* Bounds native work; a longer hint list or rewrite chain abstains. *)
let max_references = 16

let rec unlocated = function
  | EcLocation.LocError (_, exn) -> unlocated exn
  | exn -> exn

let same_location (left : EcLocation.t) (right : EcLocation.t) =
  left.EcLocation.loc_bchar = right.EcLocation.loc_bchar
  && left.EcLocation.loc_echar = right.EcLocation.loc_echar

(* EasyCrypt's verdict on [tactics] at the current proof, with the exception
   it rejected them with.  An assertion is no verdict: the caller abstains. *)
let rejection tactics =
  try ignore (run_tactics tactics); `Accepted with
  | (Out_of_memory | Stack_overflow) as exn -> raise exn
  | Assert_failure _ -> `Indeterminate
  | exn -> `Rejected exn

let rejection_message exn =
  match tactic_rejection_json exn
      ~invalid_shape:"tactic target is not convertible to the current goal"
  with
  | Some error -> Some (error_message error)
  | None -> None

let goal_hyps () = EcCoreGoal.FApi.tc1_hyps (current_tcenv1 ())

let operation_env () = EcScope.env (EcCommands.current ())

let claim ~family ~resource ~argument_kind ~failure_kind ~message payload = {
  Realizer.failure_kind;
  core = Some {
    Realizer.family;
    resource;
    argument_kinds = [argument_kind];
    side = "";
    error_message = message;
    application_head = `Null;
  };
  payload = `Assoc payload;
}

(* ------------------------------------------------------------------ *)
(* smt hints *)

let hint_name (hint : EcParsetree.pdbmap1) =
  EcSymbols.string_of_qsymbol (EcLocation.unloc hint.EcParsetree.pht_name)

let hint_identity (hint : EcParsetree.pdbmap1) =
  (hint.EcParsetree.pht_flag, hint.EcParsetree.pht_kind, hint_name hint)

(* Only [smt(h1 ... hn)]: one plain [smt] whose sole option is its hint
   list.  Other options change which provers run or which lemmas they get. *)
let plain_smt_hints tactics =
  match tactics with
  | [{ EcParsetree.pt_core = core; pt_intros = [] }] -> begin
      match located_desc core with
      | EcParsetree.Plogic (EcParsetree.Psmt infos)
        when { infos with EcParsetree.plem_wanted = None }
             = EcParsetree.empty_pprover ->
          infos.EcParsetree.plem_wanted
      | _ -> None
    end
  | _ -> None

(* [process_dbhint] resolves a lemma hint with [Ax.lookup_opt] and a theory
   hint with [Theory.lookup_opt], in the operation's (global) environment. *)
let hint_resolves env (hint : EcParsetree.pdbmap1) =
  let name = EcLocation.unloc hint.EcParsetree.pht_name in
  match hint.EcParsetree.pht_kind with
  | `Lemma -> Option.is_some (EcEnv.Ax.lookup_opt name env)
  | `Theory -> Option.is_some (EcEnv.Theory.lookup_opt name env)

let is_blank c = c = ' ' || c = '\t'

(* The agent's exact text with one hint's name removed and one separator
   kept between its neighbours.  A written [+]/[-] flag belongs to the hint,
   so a flagged hint has no candidate. *)
let text_without_hint tactic (location : EcLocation.t) =
  let length = String.length tactic in
  let start = location.EcLocation.loc_bchar in
  let stop = location.EcLocation.loc_echar in
  if start <= 0 || stop > length || start >= stop then None else
  let rec back index =
    if index > 0 && is_blank tactic.[index - 1] then back (index - 1)
    else index in
  let rec forward index =
    if index < length && is_blank tactic.[index] then forward (index + 1)
    else index in
  let before = back start in
  let after = forward stop in
  if before = 0 || tactic.[before - 1] = '+' || tactic.[before - 1] = '-'
  then None else
  let head = String.sub tactic 0 before in
  let tail = String.sub tactic after (length - after) in
  let separator =
    if tail = "" || tail.[0] = ')' || head.[String.length head - 1] = '('
    then "" else " " in
  let text = head ^ separator ^ tail in
  if not (String.starts_with ~prefix:"smt" text) then None else Some text

(* Under a compound handoff the failing stage is diagnosed in the scratch
   proof of the accepted prefix, and [t1; t2] runs [t2] on every goal [t1]
   leaves.  A candidate is checked at the focused goal only, so it is offered
   only when the prefix left that one goal. *)
let stage_runs_on_one_goal () =
  match !diagnostic_proof_override with
  | None -> true
  | Some scratch ->
      List.length (EcCoreGoal.all_opened scratch)
      = List.length (EcCoreGoal.all_opened (reconstructed_current_proof ()))

(* The candidate must parse back to the agent's [smt] with exactly that one
   hint removed, and EasyCrypt must accept it with progress here. *)
let checked_candidate tactic hints index location =
  match text_without_hint tactic location with
  | None -> None
  | Some candidate ->
      let expected = List.filteri (fun position _ -> position <> index) hints
        |> List.map hint_identity in
      let parsed =
        try Option.map (List.map hint_identity)
              (plain_smt_hints (parse_tactics candidate))
        with EcParsetree.ParseError _ | Contract_error _ -> None
      in
      if parsed = Some expected
         && fst (native_tactic_execution candidate) = "accepted_changed"
      then Some (candidate,
                 List.map (fun (_, _, name) -> name) expected)
      else None

(* [tactics] is the agent's whole tactic; [hints] are those of its [smt],
   which is that tactic or, under [by], its body. *)
let smt_hint ~tactic ~offer_candidate tactics hints =
  let count = List.length hints in
  if count < 1 || count > max_references then None else
  match rejection tactics with
  | `Accepted | `Indeterminate -> None
  | `Rejected exn ->
      match unlocated exn, rejection_message exn with
      | EcScope.HiScopeError (Some location, _), Some message -> begin
          let located = List.filter_map (fun (index, hint) ->
            if same_location hint.EcParsetree.pht_name.EcLocation.pl_loc
                 location
            then Some index else None)
            (List.mapi (fun index hint -> (index, hint)) hints) in
          match located with
          | [index] ->
              let hint = List.nth hints index in
              let env = operation_env () in
              let qualifier, name = EcLocation.unloc hint.EcParsetree.pht_name in
              (* EasyCrypt stops at the first hint it cannot resolve; the
                 located hint must be that one. *)
              let earlier_resolve = List.for_all (hint_resolves env)
                (List.filteri (fun position _ -> position < index) hints) in
              if not earlier_resolve
                 || hint.EcParsetree.pht_kind <> `Lemma
                 || hint_resolves env hint
                 || qualifier <> []
                 || not (EcEnv.LDecl.hyp_exists name (goal_hyps ()))
              then None
              else
                let candidate =
                  if not offer_candidate || not (stage_runs_on_one_goal ())
                  then None
                  else checked_candidate tactic hints index
                    hint.EcParsetree.pht_name.EcLocation.pl_loc in
                Some (claim ~family:"smt" ~resource:name
                  ~argument_kind:"smt_hint"
                  ~failure_kind:"smt_hint_names_goal_hypothesis" ~message [
                    "source_operation", `String "smt";
                    "written_name", `String name;
                    "reference_position", `Int (index + 1);
                    "reference_count", `Int count;
                    "target_name", `String "";
                    "lookup_scope", `String "global_declarations";
                    "goal_hypothesis", `Bool true;
                    "declared_after_target", `Bool false;
                    "candidate_tactic", `String (match candidate with
                      | Some (text, _) -> text | None -> "");
                    "remaining_hints", `List (match candidate with
                      | Some (_, names) -> List.map (fun x -> `String x) names
                      | None -> []);
                  ])
          | _ -> None
        end
      | _ -> None

(* ------------------------------------------------------------------ *)
(* rewrite ... in H *)

let rec take count = function
  | item :: rest when count > 0 -> item :: take (count - 1) rest
  | _ -> []

(* The one named rewrite proof term of a plain rewrite item. *)
let rewrite_item_head (item : EcParsetree.rwarg) =
  match item with
  | (None, rewrite) -> begin
      match EcLocation.unloc rewrite with
      | EcParsetree.RWRw (options, [(_, term)])
        when options.EcParsetree.match_ = None -> begin
          match term.EcParsetree.fp_head with
          | EcParsetree.FPNamed (name, None) -> Some (term, name)
          | _ -> None
        end
      | _ -> None
    end
  | _ -> None

let index_of identifier locals =
  let rec scan index = function
    | [] -> None
    | (other, _) :: rest ->
        if EcIdent.id_equal identifier other then Some index
        else scan (index + 1) rest
  in scan 0 locals

(* In the proof that reaches the failing item: [name] does not resolve as a
   proof-term head in the context before [target], resolves to a goal
   hypothesis in the whole context, and that hypothesis is declared after
   [target]. *)
let hidden_by_target term (name : EcSymbols.qsymbol EcLocation.located)
    target_name =
  let tc = current_tcenv1 () in
  let hyps = EcCoreGoal.FApi.tc1_hyps tc in
  if not (EcEnv.LDecl.hyp_exists target_name hyps) then None else
  let target_id, _ = EcEnv.LDecl.hyp_by_name target_name hyps in
  let visible = EcEnv.LDecl.local_hyps target_id hyps in
  let penv = EcCoreGoal.FApi.tc1_penv tc in
  let resolve context =
    try
      Some (EcProofTerm.process_pterm
        (EcProofTerm.ptenv_of_penv context penv)
        (EcParsetree.FPNamed (name, None)))
    with
    | EcCoreGoal.TcError _
    | EcEnv.LookupFailure _
    | EcProofTerm.ProofTermError _
    | EcTyping.TyError _
    | EcEnv.LDecl.LdeclError _ -> None
  in
  let rewrite_base =
    term.EcParsetree.fp_mode = `Implicit
    && term.EcParsetree.fp_args = []
    && EcEnv.BaseRw.is_base (EcLocation.unloc name)
         (EcEnv.LDecl.toenv visible)
  in
  let local_head (term : EcProofTerm.pt_ev) =
    match resolved_head term.EcProofTerm.ptev_pt with
    | EcCoreGoal.PTLocal identifier -> Some identifier
    | _ -> None
  in
  match rewrite_base, resolve visible,
        Option.bind (resolve hyps) local_head with
  | false, None, Some identifier ->
      let locals = (EcEnv.LDecl.tohyps hyps).EcBaseLogic.h_local in
      begin match index_of identifier locals, index_of target_id locals with
      (* Locals are listed newest first. *)
      | Some hypothesis_index, Some target_index
        when hypothesis_index < target_index
          && not (EcIdent.id_equal identifier target_id) ->
          Some (EcIdent.name identifier)
      | _ -> None
      end
  | _ -> None

(* [tactics] is the agent's whole tactic; [items] and [target] are those of
   its [rewrite ... in H], which is that tactic or, under [by], its body. *)
let rewrite_in tactics items (target : EcSymbols.symbol EcLocation.located)
    location =
  let count = List.length items in
  if count < 1 || count > max_references
     || List.exists (fun (focus, _) -> Option.is_some focus) items
  then None else
  let target_name = EcLocation.unloc target in
  match rejection tactics with
  | `Accepted | `Indeterminate -> None
  | `Rejected exn ->
      match rejection_message exn with
      | None -> None
      | Some message ->
          let prefix length = [{
            EcParsetree.pt_core = EcLocation.mk_loc location
              (EcParsetree.Plogic
                (EcParsetree.Prewrite (take length items, Some target)));
            pt_intros = [];
          }] in
          let opened proof = List.length (EcCoreGoal.all_opened proof) in
          let before = current_proof () in
          (* Every prefix runs from the current proof; the first rejected
             one names the item, and the accepted one before it gives the
             proof in which that item ran. *)
          let rec first length proof =
            if length > count then None else
            let verdict =
              try `Accepted (run_tactics (prefix length)) with
              | (Out_of_memory | Stack_overflow) as exn -> raise exn
              | Assert_failure _ -> `Indeterminate
              | exn -> match rejection_message exn with
                | Some _ -> `Rejected
                | None -> `Indeterminate
            in
            match verdict with
            | `Accepted after -> first (length + 1) after
            | `Rejected -> Some (length, proof)
            | `Indeterminate -> None
          in
          match first 1 before with
          | Some (position, reached) when opened reached = opened before ->
              begin match rewrite_item_head (List.nth items (position - 1)) with
              | Some (term, name)
                when fst (EcLocation.unloc name) = [] ->
                  with_diagnostic_proof reached (fun () ->
                    match hidden_by_target term name target_name with
                    | Some written ->
                        Some (claim ~family:"rewrite" ~resource:written
                          ~argument_kind:"rewrite_lemma"
                          ~failure_kind:"rewrite_name_declared_after_target"
                          ~message [
                            "source_operation", `String "rewrite";
                            "written_name", `String written;
                            "reference_position", `Int position;
                            "reference_count", `Int count;
                            "target_name", `String target_name;
                            "lookup_scope", `String "context_before_target";
                            "goal_hypothesis", `Bool true;
                            "declared_after_target", `Bool true;
                            "candidate_tactic", `String "";
                            "remaining_hints", `List [];
                          ])
                    | None -> None)
              | _ -> None
              end
          | _ -> None

(* ------------------------------------------------------------------ *)

(* The operation itself, and whether it is the whole tactic: a closing
   [by] runs its one-tactic body first. *)
let diagnosed_operation tactics =
  match tactics with
  | [{ EcParsetree.pt_core = core; pt_intros = [] }] -> begin
      match located_desc core with
      | EcParsetree.Pby (Some ([{ EcParsetree.pt_intros = []; _ }] as body)) ->
          Some (body, false)
      | _ -> Some (tactics, true)
    end
  | _ -> None

let out_of_scope_hypothesis ~tactic = function
  | Realizer.Unsupported_shape _ -> begin
      try
        let tactics = parse_tactics tactic in
        match diagnosed_operation tactics with
        | None -> None
        | Some (operation, whole) ->
            match plain_smt_hints operation, operation with
            | Some hints, _ ->
                smt_hint ~tactic ~offer_candidate:whole tactics hints
            | None, [{ EcParsetree.pt_core = core; pt_intros = [] }] -> begin
                match located_desc core with
                | EcParsetree.Plogic
                    (EcParsetree.Prewrite (items, Some target)) ->
                    rewrite_in tactics items target
                      core.EcLocation.pl_loc
                | _ -> None
              end
            | None, _ -> None
      with
      | EcParsetree.ParseError _
      | EcCoreGoal.TcError _
      | EcProofTerm.ProofTermError _
      | EcTyping.TyError _
      | EcEnv.LookupFailure _
      | EcEnv.LDecl.LdeclError _
      | Contract_error _
      | Assert_failure _ -> None
    end
  | Realizer.Parsed _ | Realizer.Parse_error _ -> None

let realizers = [
  { Realizer.kind = "hypothesis_scope_diagnosis.out_of_scope_hypothesis";
    realize = out_of_scope_hypothesis };
]
