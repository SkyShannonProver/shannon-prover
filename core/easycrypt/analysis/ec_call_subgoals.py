#!/usr/bin/env python3
"""Preview the subgoals that a `call (_: <invariant>).` will spawn.

Before committing an outer `call (_: I)` against an abstract
adversary, the agent typically wants to know:

  1. How many subgoals will this spawn? (= number of oracle procs
     the adversary can invoke, plus the residual pHL)
  2. What is each subgoal for? (which oracle proc, or "residual")
  3. Which subgoals share the invariant vs. need their own?

Without this, the agent commits the call, gets N surprise
subgoals, and has to reverse-engineer the structure. step4_1
audit 2026-04-30: Tree-0.1 spent ~5 min after committing
`call (_: 13-conjunct inv)` figuring out which of the 4 spawned
subgoals was the BNR.enc oracle vs. BNR.dec vs. init vs. residual.

Strategy (v1):
  • Run `call (_: <invariant>).` speculatively via the daemon's
    try_tactic — same path -try uses, no commit, no state change.
  • Parse the resulting goal_after raw text:
      - subgoal-count delta (= number of new subgoals)
      - active subgoal's procedure-call shape (which proc it's for)
  • Cross-reference with the trailing call's adversary type by
    parsing the source for the module type's `proc` list — gives
    the full subgoal preview without needing to navigate them.

Caveats:
  • If the invariant doesn't elaborate (parse error, type mismatch),
    daemon rejects → we surface the error verbatim, no preview.
  • If the call's adversary type isn't resolvable from source
    (deeply abstract / cross-file functor), we degrade gracefully:
    show the active subgoal + "and N-1 more (interface unresolved)".

Usage (via session_cli):
    python3 core/easycrypt/session_cli.py -d .ec_session \\
        -call-subgoals -c '<invariant body>'

Output:
    === Subgoal preview for `call (_: <invariant>)` ===

    Will spawn 5 subgoals:
      1. proc BNR(O).enc      (lhs/rhs symmetric)  ← shown active
      2. proc BNR(O).dec
      3. proc BNR(O).init
      4. proc adv.distinguish (residual pHL)
      5. ambient: invariant pre-condition

    Active subgoal preview:
      <first 20 lines of the active goal display>

    Recommended ordering:
      - Close trivial init last via auto.
      - Symmetric oracles (dec) often close with `proc; sim` if the
        invariant is a simple equality on shared state.
      - Hardest is usually enc — write its closer last; the others
        will inform what the invariant must contain.
"""
from __future__ import annotations

import re
from pathlib import Path


# Match an EC `proc` declaration anywhere in source — used to list
# the procs of a module type once we've identified the module name.
# Captures the proc name; doesn't try to extract argument types.
_MOD_TYPE_HEADER = re.compile(
    r"^\s*module\s+type\s+(?P<name>[A-Za-z_]\w*)"
    r"(?:\s*\([^)]*\))?"   # optional functor parameters
    r"\s*=\s*\{",
    re.MULTILINE,
)
def _find_module_type_procs(source: str, type_name: str) -> list[str]:
    """List the proc names declared in `module type <type_name> = { ... }`.
    Returns [] if not found."""
    for m in _MOD_TYPE_HEADER.finditer(source):
        if m.group("name") != type_name:
            continue
        body_start = m.end() - 1
        depth = 0
        body_end = -1
        for i in range(body_start, len(source)):
            ch = source[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    body_end = i
                    break
        if body_end < 0:
            return []
        body = source[body_start + 1: body_end]
        # `proc` declarations inside a module type are signature-only:
        #   proc enc(p : plain) : cipher
        # No body, terminated by newline or another `proc` / `}`.
        names: list[str] = []
        for line in body.splitlines():
            m2 = re.match(r"\s*proc\s+(?P<name>[A-Za-z_]\w*)\b", line)
            if m2:
                names.append(m2.group("name"))
        return names
    return []


def _extract_active_proc_calls(goal_text: str) -> tuple[str, str]:
    """From a pRHL goal display, extract the trailing `<@` call's
    procedure expression on each side. Returns (lhs_call, rhs_call),
    each may be empty if no trailing call is visible.

    EC's pRHL goal display is two-column with `(N)` markers between
    columns; calls can chain modules with parens (`A(O).distinguish`)
    so a flat regex isn't enough. We hand-parse:
      1. find each `<@` occurrence
      2. read chars after it until newline or column separator
      3. strip the trailing `(args)` (paren-balanced)
    """
    out: list[str] = []
    pos = 0
    while True:
        i = goal_text.find("<@", pos)
        if i < 0:
            break
        # Skip past '<@' and whitespace
        j = i + 2
        while j < len(goal_text) and goal_text[j] in " \t":
            j += 1
        # Read until newline
        end = j
        while end < len(goal_text) and goal_text[end] != "\n":
            end += 1
        chunk = goal_text[j:end]
        # Strip column-separator marker '(1)' / '(2)' / '( )' that
        # EC inserts between LHS and RHS in the two-column display.
        # Use `(?:^|\s+)` instead of `\s+` to also match a marker at
        # the chunk's start — when `<@` is followed only by whitespace
        # before the column marker (which we already skipped), the
        # chunk now begins directly with `(N)`. Earlier `\s+` required
        # leading whitespace and missed this. Audit 2026-04-30
        # chacha_poly step1 step 8: LHS `b <@` had only whitespace
        # before `(2)`, then RHS `b0 <@ A(...)` followed; predictor
        # reported corrupt LHS = `(2)  b0 <@ A(D(A, IndBlock).O).main`.
        chunk = re.split(r"(?:^|\s+)\(\s*\d*\s*\)\s+", chunk, maxsplit=1)[0].strip()
        # Known limit: when EC wraps a long call across multiple
        # lines (e.g., `b' <@\n  A.guess(gy,\n    gz * if ...)`),
        # this same-line chunk will be empty. We could chase the
        # continuation lines, but the two-column pRHL display makes
        # this column-positional rather than line-sequential —
        # mis-attributing wrapped LHS calls as RHS and vice versa.
        # The "Active subgoal verifies" line (extracted from
        # post_raw's centered `<proc> ~ <proc>` line) is the
        # authoritative source for which proc was consumed; the
        # "Active call (pre-tactic)" line is informational only.
        # Audit 2026-04-30 (elgamal cpa_ddh0): RHS A.guess wrapped
        # across 3 lines; predictor reports A.choose on the visible
        # single-line side, but Active subgoal verifies still
        # correctly shows `A.guess ~ A.guess`.
        # Strip the trailing paren-balanced (args) — find the
        # matching `(` for the last `)` and cut there.
        if chunk.endswith(")"):
            depth = 1
            k = len(chunk) - 2
            while k >= 0 and depth > 0:
                if chunk[k] == ")":
                    depth += 1
                elif chunk[k] == "(":
                    depth -= 1
                if depth == 0:
                    break
                k -= 1
            if depth == 0:
                chunk = chunk[:k].rstrip()
        if chunk:
            out.append(chunk)
        # Advance past THIS `<@` (not past the line end), so we
        # catch the second `<@` on the same line in EC's two-column
        # pRHL display where LHS and RHS sit side by side.
        pos = i + 2

    # Return the LAST `<@` per side (LHS first, RHS second). EC's
    # `call` tactic consumes the TRAILING call on each side, so the
    # last `<@` in each column is what's about to be consumed —
    # not the first. Earlier versions returned out[0]/out[1] which
    # happened to be right when only one adversary call was visible
    # (br93, PRG.P_Plog) but wrong when multiple calls were in the
    # display (elgamal cpa_ddh0: A.choose appears before A.guess in
    # source order; first `<@` in display is choose, but `call`
    # consumes guess).
    #
    # The two-column pRHL display interleaves LHS and RHS, so the
    # extracted list is LHS_1, RHS_1, LHS_2, RHS_2, ... — even
    # indices are LHS, odd are RHS. To get the LAST per side, take
    # the last even-indexed and last odd-indexed entry.
    last_lhs = ""
    last_rhs = ""
    for i, c in enumerate(out):
        if i % 2 == 0:
            last_lhs = c
        else:
            last_rhs = c
    return last_lhs, last_rhs


def _parse_remaining_count(goal_text: str) -> int:
    """Extract the `(remaining: N)` count from EC's goal header.
    Returns 0 if not found."""
    m = re.search(r"\(remaining:\s*(\d+)\)", goal_text)
    if m:
        return int(m.group(1))
    # If we see "Current goal" without `(remaining: N)`, EC has a
    # single subgoal — return 1.
    if "Current goal" in goal_text:
        return 1
    return 0


def _identify_adv_type_in_call(source: str, call_text: str) -> str | None:
    """Given a call expression like `A(O).distinguish` or
    `BNR(CPA_CCA_Orcls).enc`, identify the module-type that the
    OUTERMOST module argument inherits from.

    Returns the module-type name if found in source, else None.
    Heuristic only — does NOT do full type inference.
    """
    # Pull the outermost module name from the call.
    # Pattern: optional `Mod(...)` chain ending in `.proc`
    # Take the first identifier as the candidate.
    m = re.match(r"\s*([A-Za-z_]\w*)", call_text)
    if not m:
        return None
    mod_name = m.group(1)

    # EC supports both `:` (ascription) and `<:` (subtype) for module
    # type binding. Real proofs typically use `<:` for declare-module
    # restrictions like `declare module A <: ADV { -Mem }`. step4_1
    # audit 2026-04-30: original regex only matched `:`, missing all
    # `<:` declarations including chacha_poly's adversary bindings.
    # Functor params can use either too: `module M(A : T)` and
    # `module M(A <: T)` both occur in EC stdlib.
    _SEP = r"(?:<:|:)"
    pat1 = re.compile(
        rf"\bmodule\s+{re.escape(mod_name)}\s*"
        rf"\([^)]*{_SEP}\s*([A-Za-z_]\w*)"
    )
    m1 = pat1.search(source)
    if m1:
        return m1.group(1)
    pat2 = re.compile(
        rf"\bdeclare\s+module\s+{re.escape(mod_name)}\s*"
        rf"{_SEP}\s*([A-Za-z_]\w*)"
    )
    m2 = pat2.search(source)
    if m2:
        return m2.group(1)
    return None


def preview_subgoals(
    pre_raw: str,
    post_raw: str,
    accepted: bool,
    error_msg: str,
    invariant: str,
    source_text: str = "",
) -> str:
    """Format the subgoal preview. Inputs are pre/post goal raw text
    from -try'ing `call (_: <invariant>)`, plus the source file's
    text for module-type lookup.
    """
    if not accepted:
        return (
            f"=== Call subgoal preview ===\n"
            f"\n"
            f"`call (_: {invariant.strip()[:80]}...)` was rejected by "
            f"the daemon BEFORE we could preview subgoals:\n"
            f"\n"
            f"  {error_msg.strip() or '<no error text returned>'}\n"
            f"\n"
            f"Common causes:\n"
            f"  • invariant has a typo / unresolved name → check with `-where <ident>`\n"
            f"  • invariant uses a side annotation incorrectly "
            f"({{1}} vs {{2}}) → re-read the goal's pre to see "
            f"which side each var lives on\n"
            f"  • the trailing call doesn't take this invariant — "
            f"if it's a non-adversary call (named `call LEMMA`), "
            f"use `call <lemma_name>` not `call (_: I)`\n"
        )

    pre_count = _parse_remaining_count(pre_raw)
    post_count = _parse_remaining_count(post_raw)
    # Total subgoals after the call. EC's `call (_: I)` consumes the
    # current pHL subgoal and produces N new ones (one per oracle the
    # adversary actually invokes, plus the residual program if any).
    # We can't reliably predict N without parsing the called proc's
    # body and matching invocations to oracle types — that's a real
    # EC type-inference task. We report the count we observe, plus
    # information we can extract from the active subgoal display.
    spawned = post_count

    # Extract which proc the active subgoal is verifying. EC's pRHL
    # display shows `<proc> ~ <proc>` on a centered line above `post =`
    # for oracle subgoals. This is more reliable than predicting from
    # source — what's in the display IS the proc, by definition.
    active_pair_re = re.compile(
        r"^\s+([A-Za-z_][\w.()]*)\s*~\s*([A-Za-z_][\w.()]*)\s*$",
        re.MULTILINE,
    )
    active_proc_lhs = ""
    active_proc_rhs = ""
    for m in active_pair_re.finditer(post_raw):
        # First match in the post raw is the active subgoal's proc pair
        active_proc_lhs = m.group(1)
        active_proc_rhs = m.group(2)
        break

    lines: list[str] = []
    lines.append("=== Call subgoal preview ===")
    lines.append("")
    lines.append(
        f"Speculative `call (_: ...).` accepted by daemon. "
        f"{spawned} subgoal(s) will be queued post-commit."
    )

    lhs_call, rhs_call = _extract_active_proc_calls(pre_raw)
    if lhs_call:
        if rhs_call:
            lines.append(
                f"Active call (pre-tactic): `... <@ {lhs_call}(...)` "
                f"(LHS) ~ `... <@ {rhs_call}(...)` (RHS)"
            )
        else:
            lines.append(f"Active call (pre-tactic): `... <@ {lhs_call}(...)`")

    if active_proc_lhs:
        lines.append(
            f"Active subgoal verifies: `{active_proc_lhs} ~ "
            f"{active_proc_rhs}` (this is subgoal 1 of {spawned})"
        )
    lines.append("")

    # Adversary-type lookup is informational only — it tells the agent
    # what the OUTERMOST module's parameter type is, NOT a prediction
    # of subgoal procs. EC's `call` actually creates one subgoal per
    # oracle proc the adversary invokes, which is the parameter type
    # of the adversary type, not the adversary type itself. Predicting
    # that requires reasoning about functor parameter signatures we
    # don't fully resolve here.
    if source_text and lhs_call:
        adv_type = _identify_adv_type_in_call(source_text, lhs_call)
        if adv_type:
            type_procs = _find_module_type_procs(source_text, adv_type)
            if type_procs:
                lines.append(
                    f"Outermost module's type: `{adv_type}` "
                    f"(declared procs: {', '.join(type_procs)})"
                )
                lines.append(
                    "  Note: the {N} subgoals queued aren't necessarily "
                    "one per proc above — EC's `call` produces one "
                    "subgoal per oracle the adversary INVOKES, plus "
                    "residual. The active subgoal's proc (shown above) "
                    "tells you which oracle this subgoal verifies."
                    .replace("{N}", str(spawned))
                )
                lines.append("")

    lines.append("Recommended next step:")
    lines.append(
        "  • Examine the active subgoal preview below — it tells you "
        "what proc this subgoal verifies and the post you must prove."
    )
    lines.append(
        "  • For the remaining subgoals, commit the call and navigate "
        "with `-status` between each. Each subgoal is one oracle "
        "equiv with the SAME invariant `I` you supplied."
    )
    lines.append("")
    lines.append("Active subgoal preview (first 20 lines):")
    for ln in post_raw.splitlines()[:20]:
        lines.append(f"  {ln}")
    return "\n".join(lines) + "\n"


def preview_from_session(session_dir: Path, invariant: str) -> str:
    """Run -try call (_: <invariant>) speculatively and produce the
    preview. Returns formatted text."""
    # Lazy imports to avoid loading daemon when not needed.
    from core.easycrypt.session_api import open_session  # type: ignore
    from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore

    session = open_session(session_dir)

    if not session.curr.exists():
        return (
            "No current goal state. Run `-start -f <file.ec>` and "
            "`-next -c '<opener>.'` to reach a `call`-eligible state "
            "first.\n"
        )

    projection = read_proof_state_projection(
        session.dir,
        live_tool_name="call-subgoals",
    )
    if projection.status in ("candidate_closed", "verified"):
        return (
            "=== Call subgoal preview ===\n"
            "\n"
            "Proof is already complete; no call subgoals remain.\n"
        )
    if projection.consistency.errors:
        return (
            "=== Call subgoal preview ===\n"
            "\n"
            "Inconsistent proof state; refusing call-subgoal preview.\n"
            + "\n".join(f"  - {e}" for e in projection.consistency.errors[:5])
            + "\n"
        )

    state = session.read_state()
    pre_raw = state.raw_for_goal_tools
    inv_text = invariant.strip().rstrip(".")
    tactic = f"call (_: {inv_text})."

    # Same daemon setup the Session.try_speculative method uses. We
    # can't just call that method because it returns a pre-formatted
    # string and we need the raw result to do our own preview
    # formatting. Replicate the setup rather than parse its output
    # (brittle).
    try:
        from core.easycrypt.daemon_backend import DaemonBackend, _split_tactics, is_disabled
    except Exception as e:
        return (
            f"=== Call subgoal preview ===\n"
            f"\n"
            f"daemon_backend import failed: {e}. -call-subgoals "
            f"requires the EC daemon (same as -try).\n"
        )
    if is_disabled():
        return (
            "=== Call subgoal preview ===\n"
            "\n"
            "EC_DAEMON_DISABLE is set; -call-subgoals requires the "
            "daemon (same as -try). Unset the env var and retry.\n"
        )
    fpath, lname = session._get_daemon_meta()
    if not fpath or not lname:
        return (
            "=== Call subgoal preview ===\n"
            "\n"
            "session_meta.json is missing file/lemma. Re-run "
            "`-start -f <file> -lemma <name>` first.\n"
        )
    fp = Path(fpath)
    if not fp.exists():
        return (
            f"=== Call subgoal preview ===\n"
            f"\n"
            f"Source file not found: {fpath}\n"
        )

    if session._daemon_backend is None:
        session._daemon_backend = DaemonBackend(session.dir, session._include_dirs)
    try:
        hist_text = session.history.read_text(encoding="utf-8")
    except Exception:
        hist_text = ""
    tactics = _split_tactics(hist_text)

    if not session._daemon_backend._sync_to(fp, lname, tactics):
        return (
            "=== Call subgoal preview ===\n"
            "\n"
            "Could not sync daemon to committed history (daemon spawn "
            "/ session open / replay failed). If a committed tactic "
            "fails on replay, -call-subgoals is unavailable until "
            "that tactic is removed via -prev.\n"
        )

    cli = session._daemon_backend._ensure_daemon()
    if cli is None:
        return (
            "=== Call subgoal preview ===\n"
            "\n"
            "Daemon connection lost.\n"
        )

    try:
        result = cli.try_tactic(session._daemon_backend._session_id, tactic)
    except Exception as e:
        return (
            f"=== Call subgoal preview ===\n"
            f"\n"
            f"Speculative -try failed: {e}\n"
        )

    accepted = bool(result.get("accepted"))
    err_msg = ""
    if not accepted:
        err = result.get("error") or {}
        if isinstance(err, dict):
            err_msg = (err.get("raw") or err.get("message")
                       or err.get("excerpt") or "")

    post_raw = ""
    goal = result.get("goal_after") or {}
    if isinstance(goal, dict):
        post_raw = goal.get("raw", "") or ""

    # Source for module-type resolution.
    source_text = ""
    for f in sorted(session_dir.glob("extracted_*.ec")):
        source_text = f.read_text(encoding="utf-8", errors="replace")
        break
    if not source_text:
        ctx = session_dir / "context.ec"
        if ctx.exists():
            source_text = ctx.read_text(encoding="utf-8", errors="replace")

    return preview_subgoals(
        pre_raw=pre_raw,
        post_raw=post_raw,
        accepted=accepted,
        error_msg=err_msg,
        invariant=invariant,
        source_text=source_text,
    )


if __name__ == "__main__":
    # CLI smoke test mode: take pre/post/invariant via files for offline
    # testing of the formatter (without needing a live daemon).
    import sys
    if len(sys.argv) < 4:
        print("Usage: python3 ec_call_subgoals.py "
              "<pre.out> <post.out> <invariant>")
        sys.exit(1)
    pre = Path(sys.argv[1]).read_text()
    post = Path(sys.argv[2]).read_text()
    inv = sys.argv[3]
    print(preview_subgoals(pre, post, accepted=True, error_msg="",
                            invariant=inv, source_text=""))
