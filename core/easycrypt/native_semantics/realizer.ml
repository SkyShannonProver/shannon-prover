(* Feature-neutral interface between an attempt diagnosis and the features
   that can realize a failed attempt.

   A realizer belongs to one feature and names one realization kind.  The
   companion runs only the realizers whose kinds the request names, which the
   compiler derives from the features its activation plan executes.  Every
   requested realizer sees the same trigger; none sees another's claim.  No
   claim leaves the attempt without a realization, one claim realizes it, and
   several claims are an ambiguity the companion reports instead of
   choosing. *)

open Native_semantic_support

(* What EasyCrypt made of the rejected tactic. *)
type trigger =
  | Parsed of attempted_tactic
      (* A supported attempted operation that EasyCrypt rejected with a
         blocker at the current goal. *)
  | Parse_error of string
      (* EasyCrypt could not parse the tactic; the payload is its message. *)
  | Unsupported_shape of string
      (* EasyCrypt parsed the tactic, but not as a supported attempted
         operation; the payload is the reason. *)

(* The attempted operation a realizer describes when EasyCrypt did not parse
   the tactic as a supported operation. *)
type core = {
  family : string;
  resource : string;
  argument_kinds : string list;
  side : string;
  error_message : string;
  application_head : Yojson.Safe.t;
}

type claim = {
  failure_kind : string;
  core : core option;  (* required exactly when the trigger is not [Parsed] *)
  payload : Yojson.Safe.t;
}

type t = {
  kind : string;
  realize : tactic:string -> trigger -> claim option;
}

type result =
  | Unrealized
  | Realized of string * claim
  | Ambiguous of string list

let realize realizers ~kinds ~tactic trigger =
  let claims = List.filter_map (fun realizer ->
    if not (List.mem realizer.kind kinds) then None
    else match realizer.realize ~tactic trigger with
      | None -> None
      | Some claim ->
          let core_required = match trigger with
            | Parsed _ -> false
            | Parse_error _ | Unsupported_shape _ -> true
          in
          if claim.failure_kind = ""
             || Option.is_some claim.core <> core_required
          then invalid_arg ("realizer " ^ realizer.kind ^ " broke its contract");
          Some (realizer.kind, claim)) realizers
  in
  match claims with
  | [] -> Unrealized
  | [(kind, claim)] -> Realized (kind, claim)
  | many -> Ambiguous (List.map fst many)
