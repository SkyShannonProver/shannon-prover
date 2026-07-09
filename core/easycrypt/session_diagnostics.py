"""Compiler-style diagnostics for EasyCrypt session state."""
from __future__ import annotations

import re


def explain_no_progress(tactic: str, goal_raw: str) -> str:
    """Build a context-driven explanation for why ``tactic`` is a no-op."""
    t = tactic.strip().rstrip(".").strip()

    m = re.match(
        r"^inline\s+(?:\{[12]\}\s+)?(?:(\d+)|([A-Za-z_][\w.]*))",
        t,
    )
    if m:
        named = m.group(2)
        if named:
            user_parts_check = named.split(".")
            target_visible = named in goal_raw
            if not target_visible and len(user_parts_check) >= 2:
                head_mod = user_parts_check[0]
                proc = user_parts_check[-1]
                wrapped_pattern = (
                    rf"\b{re.escape(head_mod)}\s*\([\s\S]{{0,800}}\)"
                    rf"\s*\.\s*{re.escape(proc)}\b"
                )
                if re.search(wrapped_pattern, goal_raw):
                    target_visible = True
            if target_visible:
                return (
                    f"`{named}` appears to be called in the goal "
                    f"(possibly with module wrappers), but the inline "
                    f"produced no change. Possible: the call was already "
                    f"inlined in a prior step, or the form requires a "
                    f"different inline variant (e.g. `inline {{1}} N` "
                    f"for positional)."
                )

            user_parts = named.split(".")
            if len(user_parts) >= 2:
                user_mod = user_parts[0]
                siblings = sorted(set(re.findall(
                    rf"\b{re.escape(user_mod)}\.\w+\b",
                    goal_raw,
                )))
                siblings = [s for s in siblings if s != named]
                if siblings:
                    return (
                        f"Module `{user_mod}` IS in the current "
                        f"program, but the only visible references to "
                        f"it are: `{', '.join(siblings[:5])}`"
                        f"{' ...' if len(siblings) > 5 else ''}"
                        f" - not `{named}`. Did you mean one of those?"
                    )

                arg_wrappers = sorted(set(re.findall(
                    rf"\b([A-Z]\w*)\s*\([^)]*?\b{re.escape(user_mod)}\b",
                    goal_raw,
                )))
                arg_wrappers = [w for w in arg_wrappers if w != user_mod]
                if arg_wrappers:
                    return (
                        f"`{user_mod}` is passed as a MODULE ARGUMENT to "
                        f"`{', '.join(arg_wrappers[:3])}` - it's not the "
                        f"call site itself. To reach `{user_mod}`'s "
                        f"procedure body, inline the wrapper first "
                        f"(e.g. `inline {arg_wrappers[0]}.<proc>`) which "
                        f"will expose any internal calls to `{user_mod}`. "
                        f"Or check `{user_mod}`'s module declaration in "
                        f"the source file to see which procedures it "
                        f"actually exports."
                    )

            visible_refs = sorted(set(re.findall(
                r"\b[A-Z]\w*\.\w+\b",
                goal_raw,
            )))
            if visible_refs:
                return (
                    f"`{named}` is not called anywhere in the current "
                    f"program. Visible `Module.proc` references in goal: "
                    f"`{', '.join(visible_refs[:6])}`"
                    f"{' ...' if len(visible_refs) > 6 else ''}. "
                    f"Either the procedure was already inlined by an "
                    f"earlier `inline *`, or the name doesn't match any "
                    f"callable in scope."
                )
            return (
                f"`{named}` is not called anywhere in the current "
                f"program (no `Module.proc` references visible). "
                f"Goal may already be fully inlined."
            )

    m = re.match(r"^rewrite\s+(?:-)?\s*([A-Za-z_]\w*)", t)
    if m:
        lemma = m.group(1)
        return (
            f"`rewrite {lemma}` accepted but didn't change the goal - "
            f"likely the LHS pattern of `{lemma}` doesn't unify with "
            f"any subterm in the current goal. Run "
            f"`-sig {lemma}` to see its statement, then check whether "
            f"the LHS shape appears in the goal."
        )

    if re.match(r"^call\b", t):
        return explain_call_no_progress(t, goal_raw)

    m = re.match(
        r"^have\s+->.*?:.*?(?P<lhs>\S.*?)\s*=\s*(?P<rhs>\S.*?)"
        r"\s+by\s+(?P<by>.+?)\.?$",
        t,
        re.DOTALL,
    )
    if m:
        by_tac = m.group("by").strip().lower()
        reduction_only = bool(re.match(
            r"^(rewrite\s*/\w|simplify|done|trivial|/=|=>\s*/=)",
            by_tac,
        ))
        if reduction_only:
            return (
                "`have -> : LHS = RHS by <reduction-only-tactic>` "
                "produced no goal change. The most likely cause: "
                "EC's definitional reduction already collapses "
                "LHS and RHS to the same internal form before the "
                "substitution runs, so the `->` rewrite target "
                "isn't visibly present in the goal. Common examples: "
                "`(fun _ => true)` is definitionally `predT`, "
                "`(fun x => x)` is definitionally `idfun`, and "
                "eta-equivalent lambdas. Action: check whether the "
                "goal already shows the RHS form; if so, skip this "
                "step and proceed."
            )

    return ""


def explain_call_no_progress(tactic: str, goal_raw: str) -> str:
    """Compiler-style diagnostic for ``call`` no-effect on pRHL goals."""
    hints: list[str] = []
    left_top: list = []
    right_top: list = []
    compressed = _latest_goal_text(goal_raw)

    try:
        from core.easycrypt.analysis.swap_align import parse_prhl_goal  # type: ignore
        ar = parse_prhl_goal(compressed)
        if ar is not None:
            left_top = [s for s in ar.left if s.depth == 1]
            right_top = [s for s in ar.right if s.depth == 1]
    except Exception:
        pass

    def trailing_non_call(stmts: list) -> tuple[int, list[str]]:
        if not stmts:
            return 0, []
        last_call_idx = -1
        for i in range(len(stmts) - 1, -1, -1):
            if stmts[i].stmt_type == "CALL":
                last_call_idx = i
                break
        if last_call_idx == -1:
            return -1, []
        tail = stmts[last_call_idx + 1:]
        return len(tail), [s.text.strip() for s in tail[:3]]

    if left_top and right_top:
        left_trailing_n, left_trailing_sample = trailing_non_call(left_top)
        right_trailing_n, right_trailing_sample = trailing_non_call(right_top)
    else:
        left_trailing_n, right_trailing_n = 0, 0
        left_trailing_sample, right_trailing_sample = [], []

    def suggest_for_side(
        side_label: str,
        side_idx: int,
        trailing_n: int,
        trailing_sample: list[str],
        stmts: list,
    ) -> str:
        if trailing_n == 0:
            return ""
        if trailing_n == -1:
            return (
                f"{side_label} has NO `<@` procedure call at all - "
                f"`call` tactic requires a procedure call to operate "
                f"on. If you intended to enter a `Module.proc` body, "
                f"use `proc.` instead. If the procedure was already "
                f"inlined and the body is plain code, use `wp` / `sp` "
                f"/ `seq` / `if` / `while` to advance the program."
            )
        tail_types = {s.stmt_type for s in stmts[-trailing_n:]}
        if tail_types == {"ASSIGN"}:
            tac = "`wp.` (or `sp.` if the assigns are above the call)"
        elif "SAMPLE" in tail_types:
            seq_cmd = (
                f"seq {len(stmts) - trailing_n} 0"
                if side_idx == 1
                else f"seq 0 {len(stmts) - trailing_n}"
            )
            tac = (
                f"`{seq_cmd} : (<your-invariant>)` "
                f"(can't `wp` a SAMPLE - seq splits it off)"
            )
        else:
            seq_cmd = (
                f"seq {len(stmts) - trailing_n} 0"
                if side_idx == 1
                else f"seq 0 {len(stmts) - trailing_n}"
            )
            tac = (
                f"`{seq_cmd} : (<your-invariant>)` to peel the "
                f"trailing {trailing_n} statement(s) before the call"
            )
        samples = ", ".join(f"`{t}`" for t in trailing_sample)
        return (
            f"{side_label} has {trailing_n} statement(s) AFTER "
            f"the last `<@` call ({samples}) - `call` needs both "
            f"sides ending in a single trailing `<@`. Try {tac} "
            f"to align first."
        )

    if left_trailing_n != 0:
        hints.append(suggest_for_side(
            "LHS", 1, left_trailing_n, left_trailing_sample, left_top,
        ))
    if right_trailing_n != 0:
        hints.append(suggest_for_side(
            "RHS", 2, right_trailing_n, right_trailing_sample, right_top,
        ))

    glob_re = re.compile(r"\bglob\s+([A-Z]\w*)\b")
    glob_matches = sorted(set(glob_re.findall(tactic)))
    if glob_matches:
        mods = ", ".join(f"`glob {m}`" for m in glob_matches)
        hints.append(
            f"The invariant includes {mods}. If any of those modules "
            f"is an abstract adversary, EC handles its glob implicitly "
            f"via the abstract module's frame condition. Including "
            f"`={{glob X}}` explicitly can cause `call` to fail with "
            f"'no effect' on unification. Try removing `={{glob X}}` "
            f"from the invariant and threading it via the byequiv pre."
        )

    if not hints:
        return (
            "`call` accepted but produced no progress, and the goal "
            "passes the structural single-trailing-call check. The "
            "remaining likely cause is a pre/post mismatch or an "
            "invariant the unifier can't apply. Run `-tactic-forms "
            "call` for the full trap list."
        )
    return " ".join(hints)


def _latest_goal_text(goal_raw: str) -> str:
    try:
        from core.easycrypt.session_state import extract_active_goal_block  # type: ignore
    except Exception:
        try:
            from core.easycrypt.session_state import extract_active_goal_block  # type: ignore
        except Exception:
            return goal_raw
    try:
        block, _remaining = extract_active_goal_block(goal_raw)
        return block or goal_raw
    except Exception:
        return goal_raw
