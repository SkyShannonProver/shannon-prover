#!/usr/bin/env python3
"""Interactive EasyCrypt session CLI for step-by-step proof development.

Core commands:
  -start              Start a new session (wipes prior state)
  -start -f F         Start with .ec file F as frozen context
  -next -c 'T'        Apply tactic T and show resulting goal state
  -prev               Undo last tactic

Mini tools (built on top of session state):
  -lemma L            With -start -f: extract section-local lemma L into
                      standalone context (handles declare module/axiom,
                      local modules, proof replacement). Agent never needs
                      to manually create test files for section lemmas.
                      See core/easycrypt/lemma_extract.py.
  -align              Analyze current pRHL two-column goal and suggest swap
                      alignment. Parses left/right programs, matches CALLs
                      by procedure name and SAMPLEs by distribution, detects
                      variable dependencies and CALL barriers, suggests
                      swap{1}/swap{2} tactics. Use after proc; inline *.
                      NOTE: if the goal is an equiv (before proc) and the
                      right program has a while-loop, run -bridge-lemmas
                      FIRST — inline * would unroll the loop, which is wrong.
                      See core/easycrypt/swap_align.py.

  -bridge-lemmas      For an equiv goal 'L.proc ~ R.proc', scan the context
                      for equiv lemmas whose LHS/RHS matches the goal's
                      programs and suggest transitivity composition.  Use
                      this INSTEAD OF proc; inline * when the goal involves
                      a while-loop sampling procedure (e.g. rejection
                      sampling): inlining would produce an unmanageable
                      loop body.  The tool performs BFS up to depth 3 to
                      find chains of bridge lemmas and outputs ready-to-use
                      transitivity tactic templates with the intermediate
                      program filled in.  Call this before proc whenever
                      you see a sampling equiv goal.
                      See core/easycrypt/ec_bridge_lemmas.py.

  -search QUERY       Search EasyCrypt theories + loaded context for
                      lemma/axiom/op names matching QUERY (regex). Replaces
                      manual grepping through easycrypt-src/theories/.
                      See core/easycrypt/ec_search.py.
  -clones             List all clone declarations in loaded context and
                      include dirs, with their lemma renamings (e.g.,
                      dunifin_ll -> dbool_ll). Helps find clone-renamed
                      lemma names. See core/easycrypt/ec_search.py.
  -chain -c 'T1. T2.' Apply tactics one by one, stop at first error,
                      auto-rollback the failed tactic, show goal state
                      at failure point. Much faster than writing proof
                      to file and running full EC check (seconds vs
                      5-8 minutes per iteration).
                      Use --keep-on-fail to skip rollback: when sub-tactic k
                      fails, preserve state after sub-tactics 1..k-1 and
                      report partial success. Lets you continue from the
                      checkpoint instead of replaying the known-good prefix.
  -diagnose           Read the latest error from the session output,
                      match against known error patterns (from A/B test
                      failures), suggest likely cause and fix. Use this
                      BEFORE giving up on a tactic — the error may have
                      a simple fix. See core/easycrypt/ec_diagnose.py.
  -inv-from-lemma L   Extract the invariant from a local equiv lemma L
                      and format it as a ready-to-use call (_: bad, Inv)
                      template. Strips the !bad and arg-equality clauses
                      from the lemma's precondition. Use BEFORE writing
                      a call block to avoid invariant mismatches with the
                      oracle lemma's pre. See core/easycrypt/ec_inv_from_lemma.py.

  -show-proof         Print the currently accepted tactic sequence from
                      history.ec (the clean sequence after all undos).
                      Useful to collect the final proof without re-reading
                      through the interactive session output. Call this
                      after the proof is complete (after qed. is accepted)
                      to get a copy-paste-ready proof block. Unlike reading
                      the raw history file, this command also counts steps
                      and marks if qed is present.

  -write-back         Write the completed proof from session history back
                      into the source .ec file, replacing the proof block
                      for the target lemma. The source file and lemma name
                      are read from session metadata (set by -start -f ...
                      -lemma ...). Override with -f and -lemma if needed.
                      Preserves all comment lines inside the original proof
                      block (e.g. (* COMPLETE THIS ... *) markers) while
                      replacing admit. with the actual proof tactics.
                      Use this INSTEAD of reading the .ec file and calling
                      the Write tool — this command handles the read+patch+
                      write internally, avoiding the Write tool's "file not
                      read" precondition error when the agent only loaded
                      the file via -start -f (frozen context).

  -verify LEMMA       Verify the proof of a single lemma without running
                      the whole .ec file. Uses lemma_extract.py to produce
                      a trimmed file ending just after LEMMA's qed., with
                      all other proofs replaced by admit. This avoids SMT-
                      dependent lemmas that appear later in the source file
                      (e.g. a shvzk lemma using why3server) from blocking
                      verification of the target. Use -f FILE to specify the
                      source file (or it is read from session metadata if
                      the session was started with -f). If the session has
                      a complete proof in history.ec (qed. present), that
                      proof is used; otherwise the proof in FILE is used.

  -file-index [-f FILE] [--json]
                      Print a structured outline of every type, op/pred,
                      axiom, module, clone, and lemma/equiv declared in FILE
                      (or the session context file if -f is omitted).
                      Use this INSTEAD of opening a file manually or grepping
                      when you need to find a lemma name, module name, or
                      understand the file's structure at a glance. Much
                      faster than reading the whole file. Add --json for
                      machine-readable output. See ec_file_index.py.

  -check-lemma LEMMA [-f FILE] [--json]
                      Validate that LEMMA is declared in FILE (or the session
                      context file). Exits 0 if found, 1 if not found.
                      On success: prints kind and location (top-level / in
                      section). On failure: prints close-match suggestions
                      (substring / common prefix) so the caller can pick the
                      right name. Call this BEFORE dispatching a proof attempt
                      to avoid wasting a full EC session on a non-existent
                      lemma. Add --json for machine-readable output.
                      See ec_file_index.py.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

# Ensure the project root is importable: session_cli is spawned directly as
# `python core/easycrypt/session_cli.py`, so only its own dir lands on sys.path —
# without the project root the package-absolute imports below would not resolve.
_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from core.easycrypt.session_runtime import Session  # type: ignore


@contextmanager
def _session_action_lock(session_dir: Path):
    """Serialize CLI actions that share one session event stream.

    The lock file lives next to the session directory rather than inside it:
    ``-start`` wipes the session directory as part of normal operation, and
    deleting an in-directory lock while it is held would defeat the guard.
    """
    import fcntl  # POSIX only; EasyCrypt sessions already rely on POSIX.

    lock_base = session_dir.expanduser()
    try:
        lock_base = lock_base.resolve()
    except Exception:
        lock_base = lock_base.absolute()
    lock_path = lock_base.with_name(f"{lock_base.name}.cli.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def main(argv=None) -> int:
    examples = (
        "Examples:\n"
        "  # Start a new session (wipes prior state)\n"
        "  easycrypt_session.py -start\n\n"
        "  # Append a single-line command via -c\n"
        "  easycrypt_session.py -next -c 'require import AllCore Distr DBool.'\n\n"
        "  # Append a multi-line block via a file with only the next block (not other things in the file)\n"
        "  ./easycrypt_session.py -next < <file_with_next_multiline_command>\n"
        "  OR use the next alteranative that uses stdin\n"
        "  # Append a multi-line block via stdin\n"
        "  cat <<'EC' | easycrypt_session.py -next\n"
        "  module type Runnable = {\n    proc run() : bool\n  }.\n\n"
        "  lemma guess_half (A <: Runnable) &m :\n    islossless A.run =>\n    Pr[ Game(A).main() @ &m : res ] = 1%r / 2%r.\n"
        "  EC\n\n"
        "  # Step back one\n"
        "  easycrypt_session.py -prev\n\n"
        "  # Use a custom session directory\n"
        "  easycrypt_session.py -d /tmp/ec-sess -start\n"
    )
    parser = argparse.ArgumentParser(
        description="Stateless EasyCrypt session driver: start, next (append), prev (undo).",
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-d", "--dir", default=None,
                        help=("Session directory. If omitted, falls back to "
                              "$EC_SESSION_DIR (set by the orchestrator when "
                              "spawning a prover subagent) and then to "
                              ".easycrypt_session. If EC_SESSION_DIR is set "
                              "and `-d` is passed explicitly but does not "
                              "match it, session_cli exits with an error "
                              "explaining which dir you belong to."))
    # ── ACTION FLAGS ─────────────────────────────────────────────
    # Pick exactly one. Argparse can't enforce mutex across multiple
    # display groups, so we do a manual check after parse_args.
    # Display groups below organize the help output by purpose.

    # === Session operations (mutate proof state) ===
    sess_grp = parser.add_argument_group(
        "Session operations (mutate proof state — pick exactly one)")
    sess_grp.add_argument("-start", action="store_true",
        help="Start a new session (wipe state). If the session has "
             "committed tactics, they are saved to "
             "<session_dir>.pre_restart.txt and the output includes a "
             "ready-to-paste replay chain. "
             "Cost: ~3s (loads context).")
    sess_grp.add_argument("--force-restart", action="store_true",
        help="Allow -start to discard committed tactics in a pinned prover "
             "session. Intended for explicit human-approved recovery only; "
             "normal prover runs should use -prev/-checkpoint/-replay.")
    sess_grp.add_argument("-next", action="store_true",
        help="Append a command block and print current state (use "
             "--deltas-only for diffs). "
             "Cost: ~50ms-3s (depends on tactic / smt).")
    sess_grp.add_argument("-prev", action="store_true",
        help="Undo last command and print current goal. "
             "Cost: ~50ms-1s.")
    sess_grp.add_argument("-try", action="store_true", dest="try_tactic",
        help="SPECULATIVE: run a tactic WITHOUT committing it. Report "
             "acceptance + error (or goal_after) and leave session state "
             "unchanged. Requires the EC daemon (auto-spawn) and a session "
             "opened with -f + -lemma. Use to validate `apply <pivot>` / "
             "arg-pattern guesses cheaply instead of commit+rollback loops. "
             "Cost: ~50-500ms (daemon).")
    sess_grp.add_argument("-chain", action="store_true",
        help="Apply tactics one by one (split on '.'), stop at first "
             "error, auto-rollback. Use --keep-on-fail to preserve state "
             "after successful prefix instead of rolling back. "
             "Cost: ~50ms-3s per sub-tactic.")
    sess_grp.add_argument("-tactic-exec", dest="tactic_exec",
        choices=["commit", "commit_chain", "undo"],
        help="Canonical Proof Interaction Manager entry point. Submit tactics "
             "with mode commit|commit_chain|undo and receive a "
             "TacticExecutionResult workspace envelope.")
    sess_grp.add_argument("-checkpoint", metavar="NAME", dest="checkpoint_name",
        help="Save current proof state as a named checkpoint (tactic list "
             "+ goal summary). Cost: ~10ms.")
    sess_grp.add_argument("-replay", metavar="NAME", dest="replay_name",
        help="Replay tactics from a saved checkpoint to restore proof "
             "state. Cost: same as -chain over saved tactics.")
    sess_grp.add_argument("-verify", metavar="LEMMA", dest="verify_lemma",
        help="Verify a single lemma by extracting a minimal trimmed file "
             "(stops after LEMMA's qed., replaces other proofs with admit). "
             "Use -f to specify the source file or rely on session metadata. "
             "Avoids SMT failures from unrelated lemmas later in the file. "
             "Cost: ~5-30s (full strict EC compile).")
    sess_grp.add_argument("-write-back", action="store_true", dest="write_back",
        help="Write the completed proof from session history back into the "
             "source .ec file, replacing the proof block for the target "
             "lemma. Source file and lemma name come from session metadata "
             "(set by -start -f -lemma). Override with -f and -lemma. "
             "Preserves comment lines inside the original proof block. "
             "Cost: ~10ms.")
    sess_grp.add_argument("-show-proof", action="store_true", dest="show_proof",
        help="Print the currently accepted tactic sequence from history.ec "
             "(clean, after all undos). Cost: ~10ms.")
    sess_grp.add_argument("-status", action="store_true",
        help="Show current proof progress: tactic count, goal type, "
             "complete/incomplete. Cost: ~10ms.")

    # === Lookup (find a known name / scope) ===
    lookup_grp = parser.add_argument_group(
        "Lookup (find a specific name or scope)")
    lookup_grp.add_argument("-where", metavar="NAME", dest="where_name",
        help="Resolve NAME structurally via EC's `print` with clone-prefix "
             "fallback. Returns kind (module/theory/op/lemma) + full body. "
             "Use INSTEAD of grep/-sig for any name lookup — `where` finds "
             "modules, theories, ops, lemmas in one shot, AND auto-resolves "
             "names from clone instances (e.g. `where ofintd` -> `C.ofintd` "
             "if it lives in `clone Subtype as C`). "
             "Cost: ~1-2s (EC subprocess).")
    lookup_grp.add_argument("-members", metavar="SCOPE", dest="members_scope",
        help="List top-level members of a theory / clone instance "
             "(modules, theories, ops, preds, lemmas, axioms, types). "
             "Names only — no bodies. Use when you see `SplitC2.foo` in "
             "the goal and want to know what ELSE SplitC2 contains, or "
             "to discover clone-generated names like `C.ofintdK` that "
             "don't appear in source text. Wraps EC's `print theory SCOPE.` "
             "Cost: ~2-3s (EC subprocess).")
    lookup_grp.add_argument("-clones", action="store_true",
        help="List clone declarations and lemma renamings in loaded "
             "context. Source-text grep — fast. For per-clone members "
             "use `-members SCOPE` (slower, AST-level). "
             "Cost: ~50ms.")
    lookup_grp.add_argument("-file-index", action="store_true", dest="file_index",
        help="Print a structured outline of types, ops, modules, clones, "
             "and lemmas in the given -f FILE (or session context file). "
             "Add --json for raw JSON. Use instead of reading/grepping "
             "the file to locate declaration names. "
             "Cost: ~50ms.")
    lookup_grp.add_argument("-lemma-index", action="store_true", dest="lemma_index",
        help="Print every lemma's name + statement (signature only; proofs are "
             "NOT shown) in the given -f FILE (or session context file). "
             "Eval-safe whole-file lemma overview for planning which lemmas to "
             "apply/rewrite/bridge with. Add --json for raw JSON. Cost: ~50ms.")
    lookup_grp.add_argument("-check-lemma", metavar="LEMMA", dest="check_lemma",
        help="Check whether LEMMA is declared in the given -f FILE (or "
             "session context file). Exits 0 if found, 1 if not found. "
             "Prints the lemma's kind/location on success, or close-match "
             "suggestions on failure. Use this BEFORE dispatching a proof "
             "attempt to catch missing/misspelled lemma names early. "
             "Cost: ~50ms.")
    lookup_grp.add_argument("-sig", metavar="NAME", dest="sig_name",
        help="[Legacy] grep-based signature lookup for lemma/axiom/op. "
             "PREFER `-where NAME` — it covers more (modules, theories, "
             "clone-resolved names). Kept as a fast-path (no EC subprocess). "
             "Cost: ~50ms.")
    lookup_grp.add_argument("-bad-trace", metavar="MODULE", dest="bad_trace_module",
        help="Scan MODULE's procedures for bad-event mutations "
             "(`<flag> <- true;`) and counter increments. Use BEFORE "
             "designing a `call (_: ... !<module>.<flag>{N} ...)` "
             "invariant for an up-to-bad / IND-CCA-with-failure proof — "
             "tells you exactly which procs can flip which flags and "
             "under what `if`-guard. Each flip the invariant doesn't "
             "explicitly track is an unguarded loophole. "
             "Cost: ~50ms (offline source scan).")
    lookup_grp.add_argument("-call-subgoals", action="store_true",
        dest="call_subgoals",
        help="Preview the subgoals that committing `call (_: I).` "
             "would spawn, without actually committing. Pair with "
             "`-c '<invariant body>'`. Speculatively applies the call "
             "via the daemon (no state change), reports the spawned "
             "subgoal count, identifies the adversary type from "
             "source, lists each oracle proc that becomes a subgoal, "
             "and shows a 20-line preview of the active subgoal. Use "
             "BEFORE committing a non-trivial `call` to know the "
             "shape of what's coming — avoids the 'commit, see N "
             "surprise subgoals, reverse-engineer' loop. "
             "Cost: ~500ms (one daemon try_tactic + source scan).")

    # === Search (find by pattern / heuristic) ===
    search_grp = parser.add_argument_group(
        "Search (find by pattern, not by exact name)")
    search_grp.add_argument("-search", metavar="QUERY",
        help="REGEX grep on .ec source files for lemma/axiom/op "
             "DECLARATIONS matching QUERY. Use for name fragments or "
             "alternation patterns. "
             "Cost: ~50ms.")
    search_grp.add_argument("-search-skeleton", metavar="QUERY",
        dest="search_skeleton",
        help="EC native AST/operator search. QUERY is one or more "
             "operator names (operator-AND: `take size`) or a term "
             "skeleton in parens (`(_ \\in take _ _)`). Returns lemmas "
             "whose statement matches. Different from `-search` (regex "
             "grep on source text): matches at the parsed-AST level. "
             "Cost: ~3-4s (EC subprocess).")
    search_grp.add_argument("-lemma-hints", action="store_true", dest="lemma_hints",
        help="Auto-suggest lemmas based on the CURRENT goal's operators "
             "(offline operator-AND index over EC stdlib). Use when stuck "
             "on a goal involving polymorphic ops (`take`, `rcons`, "
             "`mem_*`, `map`, `filter`, ...). No query argument — derives "
             "ops from the goal. "
             "Cost: ~100ms (offline index).")

    # === Goal-state analysis (read-only) ===
    goal_grp = parser.add_argument_group(
        "Goal-state analysis (read current goal, no mutation)")
    goal_grp.add_argument("-goal-info", action="store_true", dest="goal_info",
        help="Parse current goal state: classify type "
             "(pRHL/eager/hoare/phoare/ambient/probability), extract "
             "structure, suggest tactics. Returns JSON. Also auto-fires `-where` on "
             "identifiers in the goal as `[AUTO-RESOLVED-NAMES]`. "
             "Cost: ~1-2s (auto-where adds ~1.5s when goal has names).")
    goal_grp.add_argument("-goal-json", action="store_true", dest="goal_json",
        help="Emit the current goal-state JSON adapter contract. This "
             "prefers EC-native goal artifacts when present and otherwise "
             "labels stdout parsing as fallback evidence. Cost: ~10-100ms.")
    goal_grp.add_argument("-program-json", action="store_true", dest="program_json",
        help="Emit the current program-shape JSON adapter contract. This "
             "prefers EC-native program AST artifacts when present and "
             "otherwise labels pretty-program parsing as fallback evidence. "
             "Cost: ~10-100ms.")
    goal_grp.add_argument("-agent-view", action="store_true", dest="agent_view",
        help="Emit the aggregate event-native prover view: canonical "
             "proof state, current goal projection, fresh structured "
             "guidance/evidence, stale guidance, latest errors, and safe "
             "next actions. Prefer this as the consistent state snapshot "
             "when deciding what to do next. Cost: ~10-100ms.")
    goal_grp.add_argument("-episode-view", action="store_true", dest="episode_view",
        help="Emit the event-ordered prover episode timeline for this "
             "session: committed tactics, transition kinds, goal-count "
             "changes, proof statuses, and next-action categories. Use "
             "when you need to understand how the current state was reached. "
             "Cost: ~10-100ms.")
    goal_grp.add_argument("-subgoal-gap", action="store_true", dest="subgoal_gap",
        help="Decompose the current pRHL goal's pre/post into conjuncts "
             "and classify each post conjunct: PROVED-BY-PRE, LOOSE-MATCH, "
             "PROVIDED-BY-NEXT-CALL, or MISSING. Use when stuck on what "
             "facts the current invariant lacks — surfaces the gap "
             "structurally. ALSO supports `--against-lemma 'NAME args...'` "
             "for the dual mode: project a candidate named equiv's PRE "
             "against current state to see which conjuncts are covered "
             "before committing `call`/`ecall`. Pure read. "
             "Cost: ~100ms.")
    goal_grp.add_argument("-align", action="store_true",
        help="Analyze current pRHL goal and suggest swap alignment. "
             "Cost: ~50ms.")
    goal_grp.add_argument("-swap-search", action="store_true", dest="swap_search",
        help="Auto-search for valid swap alignment on current pRHL goal "
             "(bounded trial-and-error). "
             "Cost: ~5-30s (multiple EC trials).")

    # === Suggestion & diagnostics ===
    sugg_grp = parser.add_argument_group(
        "Suggestion & diagnostics (analyze and propose next step)")
    sugg_grp.add_argument("-suggest-close", action="store_true", dest="suggest_close",
        help="Analyze the current goal (must be program-free) and "
             "suggest closing tactics with relevant lemma hints. "
             "Cost: ~100ms.")
    sugg_grp.add_argument("-diagnose", action="store_true",
        help="Diagnose the latest error: suggest likely cause and fix. "
             "Cost: ~50ms.")
    sugg_grp.add_argument("-bridge-lemmas", action="store_true", dest="bridge_lemmas",
        help="For an equiv goal L.proc ~ R.proc, scan context for equiv "
             "bridge lemmas and suggest transitivity composition. Use "
             "INSTEAD of `proc; inline *` when the RHS program contains "
             "a while-loop. BFS up to depth 3 to find chains. "
             "Cost: ~200ms (source scan).")
    sugg_grp.add_argument("-inv-from-lemma", metavar="LEMMA", dest="inv_from_lemma",
        help="Extract invariant from a local equiv lemma for use in "
             "`call (_: bad, Inv)`. "
             "Cost: ~50ms.")
    sugg_grp.add_argument("-tactic-forms", metavar="NAME", dest="tactic_forms",
        help="Print the valid argument forms for a tactic (e.g. "
             "`-tactic-forms call`). Covers the tactics where agents "
             "most commonly pick the wrong form: call, apply, rewrite, "
             "byequiv, conseq, while, seq, rnd, transitivity, congr. "
             "Pure read. Cost: ~10ms.")
    sugg_grp.add_argument("-pivot-inspect",
        choices=("context", "verified", "call-site", "bridge", "rewrite",
                 "call-invariant-skeleton"),
        dest="pivot_inspect",
        help="Read-only pivot/call-site inspection. `context` is cheap "
             "static context; `verified`, `call-site`, `bridge`, `rewrite`, "
             "and `call-invariant-skeleton` may use private EasyCrypt preflight and should "
             "be requested only when that goal shape makes the extra latency "
             "useful.")
    # === Modifier options (companions to action flags) ===
    mod_grp = parser.add_argument_group(
        "Modifier options (companions, not actions)")
    mod_grp.add_argument("-c", "--command",
        help="Command block to append (alternative to stdin for -next). "
             "WARNING: if the tactic uses backticks (p.`1) or primed names "
             "(Exp', G'), use --from-file instead — these characters break "
             "shell quoting.")
    mod_grp.add_argument("--from-file", dest="from_file",
        help="Read tactic text from a file instead of -c. Avoids shell "
             "quoting issues with backticks (p.`1), apostrophes (Exp'), "
             "and other special characters.")
    mod_grp.add_argument("-f", "--file",
        help="Load an .ec file as initial context (use with -start).")
    mod_grp.add_argument("-lemma",
        help="With -start -f: extract this lemma (handles section-local "
             "lemmas automatically).")
    mod_grp.add_argument("-I", "--include-dir", action="append", default=[],
        dest="include_dirs",
        help="Extra EasyCrypt include directory (repeatable, passed as -I "
             "to easycrypt).")
    mod_grp.add_argument("-deltas-only", action="store_true",
        help="With -next, show only the delta from previous output "
             "instead of full current state.")
    mod_grp.add_argument("--keep-on-fail", action="store_true",
        dest="keep_on_fail",
        help="With -chain: when a sub-tactic fails, preserve the state "
             "after successfully applied sub-tactics (do NOT roll back). "
             "Reports partial success and the failing tactic so you can "
             "continue from the checkpoint instead of replaying the "
             "known-good prefix.")
    mod_grp.add_argument("--against-lemma", metavar="CALL",
        dest="against_lemma", default="",
        help="With -subgoal-gap: project a candidate named equiv's PRE "
             "against current state. Pass lemma name + witness args "
             "together, e.g. --against-lemma 'H_equiv x{1} M1.m{1} "
             "M2.m{1}'.")
    mod_grp.add_argument("--max-swap-attempts", type=int, default=20,
        dest="max_swap_attempts",
        help="Maximum swap attempts for -swap-search (default: 20).")
    mod_grp.add_argument("--json", action="store_true", dest="as_json",
        help="With -file-index / -check-lemma: output raw JSON instead "
             "of formatted text.")
    mod_grp.add_argument("--ec-src", default="easycrypt-src/theories",
        help="EasyCrypt theories directory for -search/-clones (default: "
             "easycrypt-src/theories).")
    mod_grp.add_argument("--max", type=int, default=30, dest="max_results",
        help="Max results for -search (default: 30).")

    args = parser.parse_args(argv)

    # Manual mutex check across action groups (argparse can't enforce mutex
    # across multiple display groups). Exactly one action flag must be set.
    _ACTION_FLAGS = (
        # session ops
        ('start', False), ('next', False), ('prev', False),
        ('try_tactic', False), ('chain', False),
        ('checkpoint_name', None), ('replay_name', None),
        ('verify_lemma', None), ('write_back', False),
        ('show_proof', False), ('status', False),
        # lookup
        ('where_name', None), ('members_scope', None),
        ('clones', False), ('file_index', False), ('lemma_index', False),
        ('check_lemma', None), ('sig_name', None),
        ('bad_trace_module', None), ('call_subgoals', False),
        # search
        ('search', None), ('search_skeleton', None), ('lemma_hints', False),
        # goal-state
        ('goal_info', False), ('goal_json', False), ('program_json', False),
        ('agent_view', False), ('episode_view', False),
        ('subgoal_gap', False), ('align', False), ('swap_search', False),
        # suggestion
        ('suggest_close', False), ('diagnose', False),
        ('bridge_lemmas', False),
        ('inv_from_lemma', None), ('tactic_forms', None),
        ('pivot_inspect', None),
    )
    _set = []
    for attr, default in _ACTION_FLAGS:
        v = getattr(args, attr, default)
        # action flag is "set" when bool True OR str non-None
        if (default is False and v) or (default is None and v is not None):
            _set.append(attr.replace('_', '-'))
    if not _set:
        parser.error(
            "no action specified. Pick one from: "
            "Session ops (-start/-next/-prev/-try/-chain/-status/...), "
            "Lookup (-where/-members/-clones/...), "
            "Search (-search/-search-skeleton/-lemma-hints), "
            "Goal-state (-goal-info/-subgoal-gap/...), "
            "Suggestion (-suggest-close/-diagnose/-bridge-lemmas/...). "
            "Run -h for the full grouped list."
        )
    if len(_set) > 1:
        parser.error(
            f"only one action flag at a time, got: {', '.join(_set)}"
        )

    # Resolve args.dir against EC_SESSION_DIR env var.
    # The orchestrator sets EC_SESSION_DIR=<tree's assigned session dir>
    # when spawning a prover subagent. This lets the subagent omit `-d`
    # entirely (common-case correctness), and lets session_cli detect the
    # case where the subagent passed `-d` explicitly but with a wrong value
    # (e.g. typo'd the default `.ec_session` instead of their assigned
    # `.ec_session_prover_tree_0_0`).
    #
    # Motivation: ChaChaPoly v7 step1 (2026-04-21) prover typed `.ec_session`
    # for a diagnostic call late in a 45-min run, misread the empty-dir
    # response as "my session was reset," re-ran `-start` in the wrong dir,
    # and lost ~13 committed tactics 11 seconds before the cap.
    _env_session_dir = os.environ.get("EC_SESSION_DIR", "").strip() or None
    _user_passed_dir = args.dir is not None
    if _user_passed_dir and _env_session_dir and args.dir != _env_session_dir:
        sys.stderr.write(
            f"\n❌ SESSION DIR MISMATCH\n"
            f"   You passed:        -d {args.dir}\n"
            f"   You belong to:     -d {_env_session_dir}  (from EC_SESSION_DIR env var)\n"
            f"\n"
            f"   Why you shouldn't use `{args.dir}`:\n"
            f"   - If it's `.ec_session` (the default name), you've typed the\n"
            f"     default instead of your tree's assigned session. Operations\n"
            f"     on the default dir will NOT affect your real proof state.\n"
            f"   - If it names another tree (e.g. .ec_session_prover_tree_0_1\n"
            f"     when you are Tree-0.0), you are about to read/modify a\n"
            f"     SIBLING tree's work — forbidden (see CLAUDE.md).\n"
            f"\n"
            f"   What to do:\n"
            f"   - Drop the `-d` arg entirely. session_cli will use\n"
            f"     EC_SESSION_DIR (= `{_env_session_dir}`) automatically.\n"
            f"   - Or pass exactly `-d {_env_session_dir}`.\n"
            f"\n"
            f"   session_cli refused this command to prevent silent data loss.\n"
        )
        return 2
    if not _user_passed_dir:
        # Default: env var, then legacy fallback.
        args.dir = _env_session_dir or ".easycrypt_session"

    # Sanitize session directory: replace shell-special characters (e.g., apostrophes
    # from EasyCrypt prime notation like Exp', G', H') with underscores. An apostrophe
    # in a directory path passed in single-quotes terminates the quoted string
    # prematurely, corrupting the entire CLI command (e.g., -d
    # '.ec_session_prover_ExpPsample_Exp'_3' -next -c 'tactic' is parsed incorrectly).
    orig_dir = args.dir
    args.dir = re.sub(r"[^a-zA-Z0-9_./-]", "_", args.dir)
    if args.dir != orig_dir:
        sys.stderr.write(
            f"[session_cli] Warning: sanitized session dir "
            f"'{orig_dir}' -> '{args.dir}'\n"
        )

    session = Session(Path(args.dir), include_dirs=args.include_dirs)

    def _tool_payload(action_name: str, mutates_proof_state: bool) -> dict:
        payload = {
            "name": action_name,
            "mutates_proof_state": mutates_proof_state,
            "session_dir": str(session.dir.resolve()),
            "file": args.file,
            "lemma": args.lemma,
            "from_file": args.from_file,
            "has_command": bool(args.command),
            "as_json": bool(getattr(args, "as_json", False)),
        }
        for attr in (
            "where_name", "members_scope", "search", "search_skeleton",
            "sig_name", "check_lemma", "bad_trace_module",
            "inv_from_lemma", "tactic_forms", "verify_lemma",
            "checkpoint_name", "replay_name", "against_lemma",
            "pivot_inspect",
        ):
            value = getattr(args, attr, None)
            if value not in (None, "", False):
                payload[attr] = value
        return payload

    def _run_action(action_name: str, handler, *, mutates_proof_state: bool) -> int:
        with _session_action_lock(session.dir):
            payload = _tool_payload(action_name, mutates_proof_state)
            # -start wipes the session directory, so a pre-call tool.called
            # event would be deleted. Emit it after the handler for that one
            # action; session.started carries the precise start-time metadata.
            if action_name != "start":
                session.emit_event("tool.called", payload)
            try:
                rc = handler(session, args)
            except Exception as e:
                session.emit_error_event("error.raised", e, {
                    "phase": "cli_action",
                    "action": action_name,
                })
                # Balance the stream at the source: a handler that raises between
                # tool.called and tool.result would otherwise leave a dangling
                # tool.called that poisons the NEXT commit's event contract (the
                # "preflight accepted, commit rejected" mislabel). -start emits
                # tool.called only AFTER the handler, so nothing is dangling there.
                if action_name != "start":
                    session.emit_event("tool.result", payload | {
                        "exit_code": 1,
                        "status": "failed",
                    })
                raise
            if action_name == "start":
                session.emit_event("tool.called", payload | {"logged_after": True})
            session.emit_event("tool.result", payload | {
                "exit_code": rc,
                "status": "ok" if rc == 0 else "failed",
            })
            return rc

    if args.start:
        from core.easycrypt.commands.session_commands import handle_start  # type: ignore
        return _run_action("start", handle_start, mutates_proof_state=True)

    if args.tactic_exec:
        from core.easycrypt.commands.commit_commands import handle_tactic_exec  # type: ignore
        action_name = {
            "commit": "next",
            "commit_chain": "chain",
            "undo": "prev",
        }[args.tactic_exec]
        return _run_action(
            action_name,
            handle_tactic_exec,
            mutates_proof_state=True,
        )

    if args.next:
        from core.easycrypt.commands.commit_commands import handle_next  # type: ignore
        return _run_action("next", handle_next, mutates_proof_state=True)

    if args.prev:
        from core.easycrypt.commands.commit_commands import handle_prev  # type: ignore
        return _run_action("prev", handle_prev, mutates_proof_state=True)

    if args.try_tactic:
        from core.easycrypt.commands.commit_commands import handle_try  # type: ignore
        return _run_action("try", handle_try, mutates_proof_state=False)

    if args.align:
        from core.easycrypt.commands.speculative_commands import handle_align  # type: ignore
        return _run_action("align", handle_align, mutates_proof_state=False)

    if args.bridge_lemmas:
        from core.easycrypt.search.handlers import handle_bridge_lemmas
        return _run_action("bridge-lemmas", handle_bridge_lemmas, mutates_proof_state=False)

    if args.search:
        from core.easycrypt.search.handlers import handle_search
        return _run_action("search", handle_search, mutates_proof_state=False)

    if args.sig_name:
        from core.easycrypt.search.handlers import handle_sig
        return _run_action("sig", handle_sig, mutates_proof_state=False)

    if args.members_scope is not None:
        from core.easycrypt.search.handlers import handle_members
        return _run_action("members", handle_members, mutates_proof_state=False)

    if args.search_skeleton is not None:
        from core.easycrypt.search.handlers import handle_search_skeleton
        return _run_action("search-skeleton", handle_search_skeleton, mutates_proof_state=False)

    if args.where_name is not None:
        from core.easycrypt.search.handlers import handle_where
        return _run_action("where", handle_where, mutates_proof_state=False)

    if args.suggest_close:
        from core.easycrypt.commands.speculative_commands import handle_suggest_close  # type: ignore
        return _run_action("suggest-close", handle_suggest_close, mutates_proof_state=False)

    if args.pivot_inspect:
        from core.easycrypt.commands.speculative_commands import handle_pivot_inspect  # type: ignore
        return _run_action("pivot-inspect", handle_pivot_inspect, mutates_proof_state=False)

    if args.clones:
        from core.easycrypt.search.handlers import handle_clones
        return _run_action("clones", handle_clones, mutates_proof_state=False)

    if args.lemma_hints:
        from core.easycrypt.search.handlers import handle_lemma_hints
        return _run_action("lemma-hints", handle_lemma_hints, mutates_proof_state=False)

    if args.inv_from_lemma:
        from core.easycrypt.commands.speculative_commands import handle_inv_from_lemma  # type: ignore
        return _run_action("inv-from-lemma", handle_inv_from_lemma, mutates_proof_state=False)

    if args.bad_trace_module:
        from core.easycrypt.commands.speculative_commands import handle_bad_trace  # type: ignore
        return _run_action("bad-trace", handle_bad_trace, mutates_proof_state=False)

    if args.call_subgoals:
        from core.easycrypt.commands.speculative_commands import handle_call_subgoals  # type: ignore
        return _run_action("call-subgoals", handle_call_subgoals, mutates_proof_state=False)

    if args.diagnose:
        from core.easycrypt.commands.inspect_commands import handle_diagnose  # type: ignore
        return _run_action("diagnose", handle_diagnose, mutates_proof_state=False)

    if args.show_proof:
        from core.easycrypt.commands.inspect_commands import handle_show_proof  # type: ignore
        return _run_action("show-proof", handle_show_proof, mutates_proof_state=False)

    if args.goal_info:
        from core.easycrypt.commands.inspect_commands import handle_goal_info  # type: ignore
        return _run_action("goal-info", handle_goal_info, mutates_proof_state=False)

    if args.goal_json:
        from core.easycrypt.commands.inspect_commands import handle_goal_json  # type: ignore
        return _run_action("goal-json", handle_goal_json, mutates_proof_state=False)

    if args.program_json:
        from core.easycrypt.commands.inspect_commands import handle_program_json  # type: ignore
        return _run_action("program-json", handle_program_json, mutates_proof_state=False)

    if args.agent_view:
        from core.easycrypt.commands.session_commands import handle_agent_view  # type: ignore
        return _run_action("agent-view", handle_agent_view, mutates_proof_state=False)
    if args.episode_view:
        from core.easycrypt.commands.session_commands import handle_episode_view  # type: ignore
        return _run_action("episode-view", handle_episode_view, mutates_proof_state=False)

    if args.checkpoint_name:
        from core.easycrypt.commands.session_commands import handle_checkpoint  # type: ignore
        return _run_action("checkpoint", handle_checkpoint, mutates_proof_state=True)

    if args.replay_name:
        from core.easycrypt.commands.session_commands import handle_replay  # type: ignore
        return _run_action("replay", handle_replay, mutates_proof_state=True)

    if args.tactic_forms:
        from core.easycrypt.search.handlers import handle_tactic_forms
        return _run_action("tactic-forms", handle_tactic_forms, mutates_proof_state=False)

    if args.subgoal_gap:
        from core.easycrypt.commands.inspect_commands import handle_subgoal_gap  # type: ignore
        return _run_action("subgoal-gap", handle_subgoal_gap, mutates_proof_state=False)

    if args.status:
        from core.easycrypt.commands.session_commands import handle_status  # type: ignore
        return _run_action("status", handle_status, mutates_proof_state=False)

    if args.verify_lemma:
        from core.easycrypt.commands.inspect_commands import handle_verify_lemma  # type: ignore
        return _run_action("verify", handle_verify_lemma, mutates_proof_state=False)

    if args.swap_search:
        from core.easycrypt.commands.speculative_commands import handle_swap_search  # type: ignore
        return _run_action("swap-search", handle_swap_search, mutates_proof_state=False)

    if args.file_index:
        from core.easycrypt.search.handlers import handle_file_index
        return _run_action("file-index", handle_file_index, mutates_proof_state=False)
    if args.lemma_index:
        from core.easycrypt.search.handlers import handle_lemma_index
        return _run_action("lemma-index", handle_lemma_index, mutates_proof_state=False)

    if args.check_lemma:
        from core.easycrypt.commands.inspect_commands import handle_check_lemma  # type: ignore
        return _run_action("check-lemma", handle_check_lemma, mutates_proof_state=False)

    if args.chain:
        from core.easycrypt.commands.commit_commands import handle_chain  # type: ignore
        return _run_action("chain", handle_chain, mutates_proof_state=True)

    if args.write_back:
        from core.easycrypt.commands.commit_commands import handle_write_back  # type: ignore
        return _run_action("write-back", handle_write_back, mutates_proof_state=True)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
