"""Tactic precheck — sanitization + policy guards at the head of a commit.

Extracted from ``session_runtime.Session.append_block`` (a cut of the Session
god-object decomposition). Pure text → outcome: it normalizes shell-quoting
artifacts and command termination, and refuses two classes of input that would
corrupt the manager-owned proof history —

  * REPL-only library-query meta-commands (``search``/``print``/``locate``),
    which EC silently accepts in the REPL but the batch compiler later rejects;
  * raw EasyCrypt proof-control commands (``undo``/``restart``/``abort``/…),
    which mutate the REPL cursor outside the manager's history/events model.

No ``Session`` state is touched: the only session-specific inputs are the session
dir name (for the redirect hints) and an ``emit`` callback so audit events fire
inline at the same point they did before, and the result carries either the
normalized ``block_text`` or a ``refusal`` string for the caller to return.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Callable, Optional

_SHELL_FILTER_ARTIFACT_RE = re.compile(
    r"'?\s*(?:2>&1|>&\d+)\s*(?:\|\s*(?:head|tail|grep|sed|awk|jq)\b.*)?$"
    r"|"
    r"'?\s*\|\s*(?:head|tail|grep|sed|awk|jq)\b.*$"
)


def _strip_shell_filter_artifact(block_text: str) -> tuple[str, bool]:
    """Strip shell filter/redirect tails that leaked into a tactic string."""
    original = block_text.rstrip()
    cleaned = _SHELL_FILTER_ARTIFACT_RE.sub("", original)
    return cleaned, cleaned != original


@dataclass
class PrecheckOutcome:
    """Result of ``precheck_tactic``.

    ``refusal`` is ``None`` when the tactic passed the guards — in that case
    ``block_text`` is the normalized command the caller should commit. When
    ``refusal`` is set, the caller returns it verbatim and commits nothing (the
    audit events were already emitted via the ``emit`` callback).

    ``trimmed`` is the rstripped tactic BEFORE the trailing-``.`` normalization —
    the form ``append_block`` records in events / displays / qed-detects
    downstream (distinct from the committed ``block_text``, which forces a ``.``).
    """
    block_text: str
    trimmed: str
    refusal: Optional[str] = None


def precheck_tactic(
    block_text: str,
    dir_name: str,
    emit: Callable[[str, dict], None],
) -> PrecheckOutcome:
    """Sanitize + guard a tactic block before it is committed.

    ``dir_name`` is the session dir's basename (for the redirect hints); ``emit``
    is the session's event sink (called inline on a refusal, exactly as the
    inlined guards used to)."""
    # Fix zsh escaping: zsh converts ! to \! even in single quotes.
    # EasyCrypt uses ! for repeat (rewrite !H, do !split, [#] !->>).
    block_text = block_text.replace('\\!', '!')

    # Fix shell apostrophe escaping: when a tactic is passed via -c '...' and
    # a primed EC name (Exp', G', H') appears in the tactic or session dir, the
    # shell may terminate the single-quote string early and append redirect
    # fragments like "' 2>&1" or "'2>&1" to the tactic string.
    # These are never valid EasyCrypt syntax — detect and strip them.
    cleaned, stripped_shell_artifact = _strip_shell_filter_artifact(block_text)
    if stripped_shell_artifact:
        sys.stderr.write(
            f"[session_cli] Warning: shell filter/redirect artifact stripped from tactic.\n"
            f"  Original:  {block_text.rstrip()!r}\n"
            f"  Cleaned:   {cleaned!r}\n"
            f"  Cause: apostrophe in a primed EC name (Exp', G', H') broke\n"
            f"         -c '...' shell quoting, leaking shell syntax into the tactic.\n"
            f"  Fix:   use stdin or heredoc to avoid shell quoting:\n"
            f"           printf '%s' 'your tactic.' | python3 session_cli.py -next\n"
            f"         or: python3 session_cli.py -next <<'TACTEOF'\n"
            f"               your tactic.\n"
            f"             TACTEOF\n"
        )
        block_text = cleaned

    # Detect unbalanced parentheses — a strong signal that the tactic was
    # truncated by shell single-quote processing (e.g. PIR.s' ends the shell
    # string early, leaving an incomplete tactic like `while (big ... PIR.s`).
    # EasyCrypt will report a parse error; this warning tells the caller WHY.
    _open_parens = block_text.count('(')
    _close_parens = block_text.count(')')
    if _open_parens != _close_parens:
        sys.stderr.write(
            f"[session_cli] Warning: tactic has unbalanced parentheses "
            f"({_open_parens} open, {_close_parens} close) — likely truncated "
            f"by shell quoting.\n"
            f"  Cause: an apostrophe in a primed EC name (e.g. PIR.s', G', H') "
            f"inside -c '...' terminates the single-quote string early.\n"
            f"  Fix:   use heredoc or stdin to pass the tactic:\n"
            f"           python3 session_cli.py -next <<'TEOF'\n"
            f"           <your full tactic>\n"
            f"           TEOF\n"
            f"  Tactic received: {block_text.rstrip()!r}\n"
        )

    trimmed = block_text.rstrip()

    # Meta-command guard: detect EC library-query commands (search, print,
    # locate) at the start of the block and reject. These are REPL-only
    # query commands; EasyCrypt's batch compiler rejects them inside a
    # proof script ("unknown operator"), and interactive EC silently
    # skips them — so they sneak into the session's history and kill the
    # subsequent full-file verification. Observed in the D4_D6 non-eval
    # run: prover put `search WhileSamplingFixedTest.` as a tactic; EC
    # accepted it silently in the REPL, the line landed in history.ec,
    # and `easycrypt <file>` died on line 53 with "unknown operator".
    # We refuse it up-front with a clear hint so the prover picks the
    # right subcommand instead of fighting a silent no-progress loop.
    _META = ("search", "print", "locate")
    _first = trimmed.lstrip().split(None, 1)
    if _first and _first[0].rstrip("([{.,;").lower() in _META:
        # Parse the argument (lemma/pattern/path the prover tried to look up)
        # so we can redirect them to the correct session_cli subcommand
        # with the argument already filled in.
        meta_word = _first[0].rstrip("([{.,;").lower()
        rest = _first[1] if len(_first) > 1 else ""
        # Extract a bareword argument (first identifier-looking token)
        _m = re.search(r"([A-Za-z_][A-Za-z0-9_.]*)", rest)
        arg = _m.group(1) if _m else ""

        # Redirect message depends on which meta-command the prover used
        if meta_word == "print" and arg:
            redirect = f"For the exact signature of `{arg}`:\n" \
                       f"    python3 core/easycrypt/session_cli.py " \
                       f"-d {dir_name} -sig {arg}\n"
        elif meta_word == "search":
            pat = arg if arg else "PATTERN"
            redirect = f"For regex lemma search:\n" \
                       f"    python3 core/easycrypt/session_cli.py " \
                       f"-d {dir_name} -search {pat}\n"
        elif meta_word == "locate":
            nm = arg if arg else "NAME"
            redirect = f"To find where `{nm}` is declared:\n" \
                       f"    python3 core/easycrypt/session_cli.py " \
                       f"-d {dir_name} -sig {nm}\n"
        else:
            redirect = f"    python3 core/easycrypt/session_cli.py " \
                       f"-d {dir_name} -sig <LEMMA_NAME>\n"

        sys.stderr.write(
            f"[session_cli] Refusing tactic: `{_first[0]}` is an EasyCrypt "
            f"library-query command, not a proof tactic.\n"
            f"  Effect in REPL: silently accepted, no goal change, but\n"
            f"    committed into history.ec — will break full-file\n"
            f"    verification with 'unknown operator'.\n"
            f"  Use the session_cli subcommand instead:\n{redirect}"
            f"  Tactic received: {trimmed!r}\n"
        )
        emit("error.raised", {
            "phase": "tactic.precheck",
            "kind": "meta_command_refused",
            "meta_command": meta_word,
            "argument": arg,
            "tactic": trimmed,
        })
        emit("tactic.result", {
            "tactic": trimmed,
            "status": "refused",
            "reason": "meta_command",
            "history_committed": False,
        })
        # Build a tight, actionable return message the prover can act on
        hint = redirect.strip()
        return PrecheckOutcome(block_text=trimmed, trimmed=trimmed, refusal=(
            "[META_COMMAND_REFUSED] `"
            + _first[0]
            + "` is a library-query meta-command, not a proof tactic. "
            + f"{hint} "
            + "Nothing was applied; session state unchanged."
        ))

    # Proof-control guard: raw EasyCrypt commands like `undo 2.` alter the
    # REPL/session cursor outside the manager's history model. They can
    # leave current.out at a bare prompt while history.ec still claims a
    # different frontier. Route these through session_cli's managed undo or
    # orchestrator restart instead.
    _PROOF_CONTROL = ("undo", "restart", "abort", "exit", "quit")
    if _first and _first[0].rstrip("([{.,;").lower() in _PROOF_CONTROL:
        control_word = _first[0].rstrip("([{.,;").lower()
        if control_word == "undo":
            redirect = (
                f"python3 core/easycrypt/session_cli.py "
                f"-d {dir_name} -tactic-exec undo"
            )
        else:
            redirect = (
                "ask the manager/human to restart or stop this proof; "
                "do not issue raw EasyCrypt lifecycle commands"
            )
        sys.stderr.write(
            f"[session_cli] Refusing tactic: `{_first[0]}` is a raw "
            f"EasyCrypt proof-control command.\n"
            f"  Effect: mutates the REPL cursor outside manager-owned "
            f"history/events and can desynchronize the agent-facing view.\n"
            f"  Use: {redirect}\n"
            f"  Tactic received: {trimmed!r}\n"
        )
        emit("error.raised", {
            "phase": "tactic.precheck",
            "kind": "proof_control_refused",
            "control_command": control_word,
            "tactic": trimmed,
        })
        emit("tactic.result", {
            "tactic": trimmed,
            "status": "refused",
            "reason": "proof_control_command",
            "history_committed": False,
        })
        return PrecheckOutcome(block_text=trimmed, trimmed=trimmed, refusal=(
            "[PROOF_CONTROL_REFUSED] `"
            + _first[0]
            + "` is a raw proof-control command. Use "
            + redirect
            + ". Nothing was applied; session state unchanged."
        ))

    # Ensure the command block ends with a '.' (last non-whitespace char)
    # so EasyCrypt doesn't wait for a terminating period.
    if trimmed and not trimmed.endswith('.'):
        block_text = trimmed + '.'
    else:
        block_text = trimmed

    return PrecheckOutcome(block_text=block_text, trimmed=trimmed)
