(* Shared, read-only reconstruction boundary for native EasyCrypt adapters. *)

open EcLib
open Yojson.Safe.Util

exception Contract_error of string

(* EasyCrypt's registered printers give the text its own toplevel shows.  An
   exception without one falls through to Why3's base printer, which prints
   "anomaly: " and the constructor; report the bare constructor instead. *)
let exception_text = function
  | EcCoreGoal.TcError error ->
      Format.asprintf "%a" EcUserMessages.pp_tc_error error
  | exn ->
      let constructor = Printexc.to_string exn in
      let text = String.trim (EcPException.tostring exn) in
      if text = "anomaly: " ^ constructor then constructor else text

let json_string name value =
  try value |> member name |> to_string
  with _ -> raise (Contract_error ("missing string field: " ^ name))

let json_string_list name value =
  try value |> member name |> to_list |> List.map to_string
  with _ -> raise (Contract_error ("invalid string-list field: " ^ name))

let json_int name value =
  try value |> member name |> to_int
  with _ -> raise (Contract_error ("missing integer field: " ^ name))

let why3_config_path () =
  match Sys.getenv_opt "SHANNON_WHY3_CONFIG" with
  | Some path when Sys.file_exists path -> Some path
  | Some _ -> raise (Contract_error "managed Why3 configuration is missing")
  | None -> raise (Contract_error "managed Why3 configuration was not bound")

(* The manager's smt portfolio and session timeout (core/easycrypt/ec_env.py),
   passed in the environment so that the companion's [smt] runs the provers
   the manager's EasyCrypt runs.  A prover the configuration does not know
   fails initialization, as it fails the CLI. *)
let smt_portfolio () =
  match Sys.getenv_opt "SHANNON_SMT_PROVERS" with
  | Some value when String.trim value <> "" ->
      Some (List.filter (fun name -> name <> "")
        (List.map String.trim (String.split_on_char ',' value)))
  | _ -> None

let smt_timeout () =
  match Sys.getenv_opt "SHANNON_SMT_TIMEOUT" with
  | None -> 3
  | Some value -> begin
      match int_of_string_opt (String.trim value) with
      | Some seconds when seconds > 0 -> seconds
      | _ -> raise (Contract_error "SHANNON_SMT_TIMEOUT is not a positive integer")
    end

let checkmode () =
  let provers = smt_portfolio () in
  {
    EcCommands.cm_checkall = false;
    cm_timeout = smt_timeout ();
    cm_cpufactor = 1;
    cm_nprovers = (match provers with Some names -> max 1 (List.length names) | None -> 1);
    cm_provers = provers;
    cm_quorum = None;
    cm_profile = false;
  }

(* The prover settings [EcCommands.initialize] gives the companion's scope
   through [EcScope.Prover.set_default], rebuilt the same way.
   [dft_prover_infos] alone names no prover, and an [smt] run with it
   proves nothing. *)
let initial_prover_infos () =
  let checkmode = checkmode () in
  let dft = EcProvers.dft_prover_infos in
  { dft with
    EcProvers.pr_provers = (match checkmode.EcCommands.cm_provers with
      | Some provers -> provers
      | None -> List.filter EcProvers.is_prover_known
          EcProvers.dft_prover_names);
    pr_timelimit = max 0 checkmode.cm_timeout;
    pr_cpufactor = max 0 checkmode.cm_cpufactor;
    pr_maxprocs = checkmode.cm_nprovers;
    pr_quorum = max 1 (Option.value ~default:dft.EcProvers.pr_quorum
      checkmode.cm_quorum);
  }

(* The scope's prover settings as the replayed commands leave them, tracked
   the way EasyCrypt's scope keeps them, since it does not export its own
   record: [prover ...] changes them (EcScope.Prover.process), and closing
   a theory returns to its parent scope and so to the parent's settings.
   Sections keep them. *)
let tracked_prover_infos : EcProvers.prover_infos option ref = ref None
let enclosing_prover_infos : EcProvers.prover_infos list ref = ref []

let scope_prover_infos () =
  match !tracked_prover_infos with
  | Some infos -> infos
  | None -> initial_prover_infos ()

let track_prover_infos action =
  match EcLocation.unloc action with
  | EcParsetree.GthOpen _ ->
      enclosing_prover_infos :=
        scope_prover_infos () :: !enclosing_prover_infos
  | EcParsetree.GthClose _ -> begin
      match !enclosing_prover_infos with
      | outer :: rest ->
          tracked_prover_infos := Some outer;
          enclosing_prover_infos := rest
      | [] -> ()
    end
  | EcParsetree.Gprover_info options ->
      tracked_prover_infos := Some
        (EcScope.Prover.pprover_infos_to_prover_infos
           (EcScope.env (EcCommands.current ()))
           (scope_prover_infos ()) options)
  | _ -> ()

let initialize include_dirs =
  tracked_prover_infos := None;
  enclosing_prover_infos := [];
  let module Sites = (val EcRelocate.sites) in
  List.iter
    (fun theory ->
      EcCommands.addidir ~namespace:`System
        (Filename.concat theory "prelude");
      EcCommands.addidir ~namespace:`System ~recursive:true theory)
    Sites.theories;
  List.iter EcCommands.addidir include_dirs;
  EcProvers.initialize ?why3conf:(why3_config_path ()) ();
  EcCorePrinting.Registry.register (module EcPrinting);
  EcUserMessages.register ();
  EcCommands.initialize
    ~restart:false ~undo:false ~boot:false ~checkmode:(checkmode ())
    ~checkproof:true

let process_file path =
  let reader = EcIo.from_file path in
  Fun.protect
    ~finally:(fun () -> EcIo.finalize reader)
    (fun () ->
      List.iteri
        (fun index command ->
          try
            ignore (EcCommands.process command.EcParsetree.gl_action);
            track_prover_infos command.EcParsetree.gl_action
          with exn -> raise (Contract_error (
            "replay command " ^ string_of_int (index + 1) ^
            " failed in " ^ Filename.basename path ^ ": " ^
            exception_text exn)))
        (EcIo.parseall reader))

let current_proof () =
  match EcScope.goal (EcCommands.current ()) with
  | Some { EcScope.puc_jdg = EcScope.PSCheck proof; _ } -> proof
  | Some { EcScope.puc_jdg = EcScope.PSNoCheck; _ } ->
      raise (Contract_error "current proof is not checked")
  | None -> raise (Contract_error "no active proof goal")

let current_tcenv1 () = EcCoreGoal.tcenv1_of_proof (current_proof ())

let goal_text () =
  Format.asprintf "%a"
    (fun formatter () -> EcCommands.pp_maybe_current_goal formatter) ()
