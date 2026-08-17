(* Shared, read-only reconstruction boundary for native EasyCrypt adapters. *)

open EcLib
open Yojson.Safe.Util

exception Contract_error of string

let exception_text = function
  | EcCoreGoal.TcError error ->
      Format.asprintf "%a" EcUserMessages.pp_tc_error error
  | exn -> Printexc.to_string exn

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

let initialize include_dirs =
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
    ~restart:false ~undo:false ~boot:false
    ~checkmode:{
      EcCommands.cm_checkall = false;
      cm_timeout = 3;
      cm_cpufactor = 1;
      cm_nprovers = 1;
      cm_provers = None;
      cm_quorum = None;
      cm_profile = false;
    }
    ~checkproof:true

let process_file path =
  let reader = EcIo.from_file path in
  Fun.protect
    ~finally:(fun () -> EcIo.finalize reader)
    (fun () ->
      List.iteri
        (fun index command ->
          try ignore (EcCommands.process command.EcParsetree.gl_action)
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
