(* smt_failure_localization: the first smt call of a rejected tactic that
   EasyCrypt cannot prove, located in the tactic text, how many goals it
   fails on, and, when it can be established, what kind of goal the first
   failed one is.

   EasyCrypt owns every verdict.  The tactic runs twice at the proof the
   query runs against (the current goal, or the scratch proof of a recovery
   handoff):

   - in report mode, where a failed smt call is reported with its source
     location as a critical notice, its goal is admitted and the run goes
     on; and
   - in strict mode, as the toplevel runs it.

   Every smt (and coq) call asks the provers callback for its settings just
   before it runs, so counting those calls numbers the calls in execution
   order.  Up to the first failed call the two runs execute the same tactics
   on the same goals: only a failed smt or coq call behaves differently
   between the modes.  The first report is kept only when the strict run
   stops at the same call number with an uncatchable tactic error, which in
   this EasyCrypt only a strict smt or coq call raises (EcLowGoal.t_smt and
   t_coq).  The report must also be the smt failure notice of a located call
   inside the tactic text; a coq failure or an unlocated call (an intro
   pattern [/#] reports no location) yields no claim.

   The kind of the first failed goal needs that goal, which EasyCrypt does
   not export from a run.  It is re-derived only for a call that the parse
   tree reaches through stage sequences, [try], [by], parentheses, [first],
   [last] and [[ | ]] branches: EasyCrypt runs the stages before the call on
   each goal, then the call alone on each goal it reaches, in execution
   order, and the first goal that fails strictly is the one described.
   When the call is the tactic's first stage and the first call to fail,
   its failed goal is the goal the tactic runs on and nothing is re-run.
   Anywhere else, or when that run does not reproduce the failure, the kind
   is left empty and nothing is said about it.

   Each phase has a wall-clock bound, checked before every smt call (a call
   that has started cannot be interrupted). *)

open EcLib
open EcParsetree
open Native_semantic_support

exception Over_budget
exception Unroutable

let report_seconds = 4.0     (* report run, up to the first failure *)
let count_seconds = 1.0      (* report run, counting after the first one *)
let shape_seconds = 2.0      (* re-deriving the first failed goal *)

(* The strict run reaches the failed call by the same calls the report run
   made before it, so it gets that time again with some slack. *)
let strict_seconds report_elapsed = 0.5 +. 1.25 *. report_elapsed

let now () = Unix.gettimeofday ()

type counter = { mutable calls : int; mutable deadline : float }

let counting_ttenv ~mode counter =
  let scope = EcCommands.current () in
  { EcHiGoal.tt_provers = (fun options ->
      if now () > counter.deadline then raise Over_budget;
      counter.calls <- counter.calls + 1;
      match options with
      | None -> scope_prover_infos ()
      | Some options ->
          EcScope.Prover.pprover_infos_to_prover_infos
            (EcScope.env scope) (scope_prover_infos ()) options);
    tt_smtmode = mode;
    tt_implicits = EcScope.Options.get_implicits scope;
    tt_oldip = EcScope.Options.get scope "oldip";
    tt_redlogic = EcScope.Options.get scope "redlogic"; }

let rec uncatchable = function
  | EcLocation.LocError (_, exn) -> uncatchable exn
  | EcCoreGoal.TcError error when not error.EcCoreGoal.tc_catchable ->
      Some error
  | _ -> None

let fatal = function Out_of_memory | Stack_overflow -> true | _ -> false

type report = {
  first_call : int;        (* number of the first failed call *)
  first_notice : string;   (* its notice, which names its location *)
  failures : int;          (* notices of that same call *)
  complete : bool;         (* the report run finished *)
  elapsed : float;         (* seconds until the first notice *)
}

let report_run tactics =
  let started = now () in
  let counter = { calls = 0; deadline = started +. report_seconds } in
  let notices = ref [] in
  let first_at = ref started in
  let gstate = EcEnv.gstate (EcCoreGoal.FApi.tc1_env (current_tcenv1 ())) in
  let notifier level message =
    if level = `Critical then begin
      if !notices = [] then begin
        first_at := now ();
        counter.deadline <- !first_at +. count_seconds
      end;
      notices := (counter.calls, Lazy.force message) :: !notices
    end
  in
  let nid = EcGState.add_notifier notifier gstate in
  let finished =
    Fun.protect ~finally:(fun () -> EcGState.rem_notifier nid gstate)
      (fun () ->
        try
          ignore (EcHiTacticals.process
            (counting_ttenv ~mode:`Report counter) tactics (current_proof ()));
          true
        with exn when not (fatal exn) -> false)
  in
  match List.rev !notices with
  | [] -> None
  | (call, notice) :: _ as all -> Some {
      first_call = call;
      first_notice = notice;
      failures = List.length (List.filter (fun (_, item) -> item = notice) all);
      complete = finished;
      elapsed = !first_at -. started;
    }

(* The strict run's failing call number and error, when it stops with the
   uncatchable error of a strict smt or coq call. *)
let strict_run ~report_elapsed tactics =
  let counter = {
    calls = 0; deadline = now () +. strict_seconds report_elapsed } in
  match EcHiTacticals.process
      (counting_ttenv ~mode:`Strict counter) tactics (current_proof ()) with
  | _ -> None
  | exception exn when not (fatal exn) ->
      Option.map (fun error -> (counter.calls, error)) (uncatchable exn)

(* The byte span of the call a smt failure notice names.  The notice is
   [EcLocation.tostring loc ^ ": smt call failed"]; a tactic parsed from a
   string has an empty file name and lines counted from 1.  The location is
   read back only when rendering it again gives the same text, and only a
   one-line span inside the tactic is accepted. *)
let failed_call_span tactic notice =
  let suffix = ": smt call failed" in
  let length = String.length notice and suffix_length = String.length suffix in
  if length <= suffix_length
     || String.sub notice (length - suffix_length) suffix_length <> suffix
  then None else
  let rendered = String.sub notice 0 (length - suffix_length) in
  match Scanf.sscanf rendered ": line %d (%d-%d)%!"
      (fun line first last -> (line, first, last)) with
  | exception (Scanf.Scan_failure _ | Failure _ | End_of_file
               | Invalid_argument _) -> None
  | (line, first, last) ->
      let location = { EcLocation._dummy with
        EcLocation.loc_fname = "";
        loc_start = (line, first);
        loc_end = (line, last); } in
      if EcLocation.tostring location <> rendered || line < 1
         || first < 0 || last <= first then None else
      let rec line_start index remaining =
        if remaining = 1 then Some index
        else match String.index_from_opt tactic index '\n' with
          | Some newline -> line_start (newline + 1) (remaining - 1)
          | None -> None
      in
      match line_start 0 line with
      | None -> None
      | Some base ->
          let start = base + first and stop = base + last in
          if stop > String.length tactic
             || String.contains (String.sub tactic start (stop - start)) '\n'
          then None
          else Some (start, stop)

(* How the parse tree reaches the failed call. *)
type path =
  | Here of ptactic_core                 (* the call itself *)
  | Try of path                          (* [try t] *)
  | Body of ptactic list * path          (* earlier stages, then this one *)
  | Branch of int * int * path           (* branch [j] of [n] in [[ | ]] *)
  | Firsts of int * path                 (* [first n t] *)
  | Lasts of int * path                  (* [last n t] *)

let covers (location : EcLocation.t) (start, stop) =
  location.EcLocation.loc_bchar <= start && stop <= location.loc_echar

let rec path_in_stages span stages =
  let rec split before = function
    | [] -> None
    | stage :: rest ->
        if covers stage.pt_core.EcLocation.pl_loc span
        then Some (List.rev before, stage)
        else split (stage :: before) rest
  in
  match split [] stages with
  | None -> None
  | Some (before, stage) ->
      Option.map (fun inner -> Body (before, inner))
        (path_in_core span stage.pt_core)

and path_in_core span (core : ptactic_core) =
  let location = core.EcLocation.pl_loc in
  match core.EcLocation.pl_desc with
  | Plogic (Psmt _)
    when location.EcLocation.loc_bchar = fst span
      && location.loc_echar = snd span -> Some (Here core)
  | Ptry inner -> Option.map (fun inner -> Try inner) (path_in_core span inner)
  | Pby (Some body) | Pseq body -> path_in_stages span body
  | Psubgoal (Psubtacs branches) ->
      let count = List.length branches in
      let rec find index = function
        | [] -> None
        | branch :: rest ->
            if covers branch.pt_core.EcLocation.pl_loc span then
              Option.map (fun inner -> Branch (index, count, inner))
                (path_in_core span branch.pt_core)
            else find (index + 1) rest
      in
      find 0 branches
  | Psubgoal (Pfirst (tactic, n)) ->
      Option.map (fun inner -> Firsts (n, inner))
        (path_in_core span tactic.pt_core)
  | Psubgoal (Plast (tactic, n)) ->
      Option.map (fun inner -> Lasts (n, inner))
        (path_in_core span tactic.pt_core)
  | _ -> None

let proof_of (goal : EcCoreGoal.pregoal) =
  EcCoreGoal.start goal.EcCoreGoal.g_hyps goal.EcCoreGoal.g_concl

(* The goals [stages] leave when EasyCrypt runs them on [goal]. *)
let run_stages ttenv stages goal =
  if stages = [] then [goal] else
  let (_, opened), proof = EcHiTacticals.process ttenv stages (proof_of goal) in
  let goals = EcCoreGoal.all_opened proof in
  if List.length goals <> List.length opened then raise Unroutable;
  goals

let rec take n = function
  | item :: rest when n > 0 -> item :: take (n - 1) rest
  | _ -> []

(* The goals the call is applied to, in execution order, computed on
   demand: a [by] or parenthesized body runs goal by goal. *)
let rec applications ttenv path goals : (ptactic_core * EcCoreGoal.pregoal) Seq.t =
  match path with
  | Here core -> Seq.map (fun goal -> (core, goal)) (List.to_seq goals)
  | Try inner -> applications ttenv inner goals
  | Body (before, inner) ->
      Seq.flat_map
        (fun goal () -> applications ttenv inner (run_stages ttenv before goal) ())
        (List.to_seq goals)
  | Branch (index, count, inner) ->
      if List.length goals <> count then raise Unroutable;
      applications ttenv inner [List.nth goals index]
  | Firsts (n, inner) ->
      if n > List.length goals then raise Unroutable;
      applications ttenv inner (take n goals)
  | Lasts (n, inner) ->
      let count = List.length goals in
      if n > count then raise Unroutable;
      applications ttenv inner (List.filteri (fun index _ -> index >= count - n) goals)

let judgment_kind (concl : EcAst.form) =
  match concl.EcAst.f_node with
  | EcAst.FhoareF _ -> "hoare_function"
  | EcAst.FhoareS _ -> "hoare_statement"
  | EcAst.FbdHoareF _ -> "phoare_function"
  | EcAst.FbdHoareS _ -> "phoare_statement"
  | EcAst.FeHoareF _ -> "ehoare_function"
  | EcAst.FeHoareS _ -> "ehoare_statement"
  | EcAst.FequivF _ -> "equiv_function"
  | EcAst.FequivS _ -> "equiv_statement"
  | EcAst.FeagerF _ -> "eager_function"
  | _ -> "formula"

(* The kind of the first goal on which the call fails strictly, or "". *)
let first_failed_goal_kind ~first_call tactics span =
  try
    match path_in_stages span tactics, EcCoreGoal.opened (current_proof ()) with
    | Some (Body ([], (Here _ | Try (Here _)))), Some (_, current)
      when first_call = 1 ->
        (* The call is the first thing the tactic runs, on the goal it is
           applied to, and it is the first call that failed: that goal is
           the failed one, so no run is needed. *)
        judgment_kind current.EcCoreGoal.g_concl
    | Some path, Some (_, current) ->
        let counter = { calls = 0; deadline = now () +. shape_seconds } in
        let ttenv = counting_ttenv ~mode:`Strict counter in
        let fails (core, goal) =
          match EcHiTacticals.process ttenv
              [{ pt_core = core; pt_intros = [] }] (proof_of goal) with
          | _ -> None
          | exception exn when not (fatal exn) ->
              if Option.is_some (uncatchable exn) then Some goal
              else raise Unroutable
        in
        begin match Seq.find_map fails (applications ttenv path [current]) with
        | Some goal -> judgment_kind goal.EcCoreGoal.g_concl
        | None -> ""
        end
    | _ -> ""
  with exn when not (fatal exn) -> ""

let localize tactic =
  match parse_tactics tactic with
  | exception (EcParsetree.ParseError _ | Contract_error _) -> None
  | tactics ->
  match report_run tactics with
  | None -> None
  | Some report ->
  match failed_call_span tactic report.first_notice with
  | None -> None
  | Some ((start, stop) as span) ->
  match strict_run ~report_elapsed:report.elapsed tactics with
  | Some (strict_call, error) when strict_call = report.first_call ->
      let message = error_message (tc_error_json error) in
      if message = "" then None else
      Some {
        Realizer.failure_kind = "smt_call_failed";
        core = Some {
          Realizer.family = "smt_call";
          resource = "";
          argument_kinds = [];
          side = "";
          error_message = message;
          application_head = `Null;
        };
        payload = `Assoc [
          "smt_call_text", `String (String.sub tactic start (stop - start));
          "smt_call_start", `Int start;
          "smt_call_end", `Int stop;
          "failed_goal_count", `Int report.failures;
          "failed_goal_count_complete", `Bool report.complete;
          "first_failed_goal_kind", `String
            (first_failed_goal_kind ~first_call:report.first_call
              tactics span);
          "report_failure_call", `Int report.first_call;
          "strict_failure_call", `Int strict_call;
        ];
      }
  | _ -> None

(* Only a tactic EasyCrypt did not parse as a supported single operation can
   hold an smt call.  Any failure of this realizer is its own abstention,
   never the batch's. *)
let first_failed_call ~tactic = function
  | Realizer.Unsupported_shape _
    when contains_substring tactic "smt" || contains_substring tactic "/#" ->
      (try localize tactic with exn when not (fatal exn) -> None)
  | _ -> None

let realizers = [
  { Realizer.kind = "smt_failure_localization.first_failed_call";
    realize = first_failed_call };
]
