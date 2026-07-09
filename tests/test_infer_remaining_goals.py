"""Validate infer_remaining_goals against real EC session behavior.

For each branching pattern, we:
  1. Set up a minimal EC session that reaches the branch point via a
     known simple tactic sequence.
  2. Run -goal-info and record what EC actually reports as num_remaining.
  3. Close each subgoal in sequence via -next + a closing tactic, and
     record the goal_type that EC reports for each.
  4. Compare against what infer_remaining_goals predicted.

Any mismatch is a bug in the inference catalog to fix.

Run: python3 tests/test_infer_remaining_goals.py
"""
import json
import subprocess
import sys
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SESSION_CLI = REPO / "core" / "easycrypt" / "session_cli.py"


def _run(args: list[str], check: bool = False) -> tuple[int, str, str]:
    """Run session_cli with given args; return (rc, stdout, stderr)."""
    try:
        r = subprocess.run(
            [sys.executable, str(SESSION_CLI)] + args,
            cwd=str(REPO), capture_output=True, text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        return (
            124,
            exc.stdout or "",
            (exc.stderr or "") + "\n[timeout] session_cli exceeded 60s",
        )
    return r.returncode, r.stdout, r.stderr


def _setup_dice_session(sdir: Path, lemma: str = "D4_D6") -> None:
    """Fresh Dice4_6 session targeting the given lemma."""
    if sdir.exists():
        shutil.rmtree(sdir)
    sdir.parent.mkdir(parents=True, exist_ok=True)
    rc, out, err = _run([
        "-d", str(sdir), "-start",
        "-f", "eval/examples/Dice4_6.ec",
        "-I", "easycrypt-src/theories",
        "-lemma", lemma,
    ])
    if rc != 0:
        raise RuntimeError(f"failed to start {lemma}: {err or out}")


def _setup_fixture_session(sdir: Path, lemma: str) -> None:
    """Fresh session targeting a lemma in tests/fixtures/branch_patterns.ec."""
    if sdir.exists():
        shutil.rmtree(sdir)
    sdir.parent.mkdir(parents=True, exist_ok=True)
    rc, out, err = _run([
        "-d", str(sdir), "-start",
        "-f", "tests/fixtures/branch_patterns.ec",
        "-I", "easycrypt-src/theories",
        "-lemma", lemma,
    ])
    if rc != 0:
        raise RuntimeError(f"failed to start {lemma}: {err or out}")


def _goal_info(sdir: Path) -> dict:
    rc, out, err = _run(["-d", str(sdir), "-goal-info"])
    if not out:
        return {}
    # -goal-info may emit diagnostic blocks before the JSON dump
    # BEFORE the JSON dump (so tool-call truncation doesn't kill the
    # auto-fire info). Extract just the JSON object by finding the first
    # `{` at line start and parsing the balanced braces.
    lines = out.splitlines(keepends=True)
    start = 0
    for i, ln in enumerate(lines):
        if ln.startswith('{'):
            start = i
            break
    json_text = ''.join(lines[start:])
    depth = 0
    end = len(json_text)
    for i, ch in enumerate(json_text):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return json.loads(json_text[:end])


def _next(sdir: Path, tac: str) -> tuple[int, str]:
    rc, out, err = _run(["-d", str(sdir), "-next", "-c", tac])
    if rc != 0:
        print(f"  FAIL applying `{tac}`: {err or out}")
    return rc, out


def _cleanup(sdir: Path) -> None:
    if sdir.exists():
        shutil.rmtree(sdir)
    pre = Path(str(sdir) + ".pre_restart.txt")
    if pre.exists():
        pre.unlink()


def _check(name: str, predicted: list[dict], actual_types: list[str]) -> bool:
    """Return True if predictions match actuals (loose: type match only).

    Types that can substitute: 'equiv' ~ 'pRHL' (classifier calls it 'equiv'
    in some cases), '(inherits prior goal type)' accepts anything.
    """
    ok = True
    if len(predicted) != len(actual_types):
        print(
            f"  ❌ {name}: predicted {len(predicted)} subgoals, "
            f"observed {len(actual_types)}"
        )
        ok = False
    for i, (p, a) in enumerate(zip(predicted, actual_types), 1):
        pt = p["predicted_type"]
        if pt.startswith("(inherits"):
            continue
        a_norm = a.lower()
        pt_norm = pt.lower()
        match = (
            pt_norm == a_norm
            or (pt_norm == "prhl" and a_norm in ("prhl", "equiv"))
            or (pt_norm == "ambient" and a_norm in ("ambient",))
        )
        if not match:
            print(f"  ❌ {name} subgoal {i}: predicted={pt}, actual={a}")
            ok = False
    if ok:
        print(f"  ✓ {name}: all {len(predicted)} subgoal types match")
    return ok


def test_have_rewrite() -> None:
    """`have -> : LHS = RHS.` with no hidden continuation should not infer one."""
    sdir = Path("/tmp/claude/infer_test_have_rewrite")
    _setup_dice_session(sdir, "D4_D6")
    for tac in [
        "move=> hf hfinv.",
        "bypr (res{1}) (finv res{2})=> />.",
        "move=> &1 &2 a.",
        "rewrite prD4.",
        "have -> : Pr[D6.sample() @ &2 : finv res = a] = Pr[D4_6.SampleWi.sample(tt, 5) @ &2 : finv res = a].",
    ]:
        _next(sdir, tac)
    gi = _goal_info(sdir)
    predicted = gi.get("remaining_goals_inference", [])
    _cleanup(sdir)
    assert predicted == []


def test_have_claim_ambient() -> None:
    """`have h : P.` with non-Pr claim → (1) ambient, (2) inherits."""
    name = "have h : P (ambient claim)"
    sdir = Path("/tmp/claude/infer_test_have_claim")
    _setup_dice_session(sdir, "prD4")
    for tac in [
        "move=> k &m.",
        "byphoare=> //.",
        "have h : 1 <= 1.",
    ]:
        _next(sdir, tac)
    gi = _goal_info(sdir)
    predicted = gi.get("remaining_goals_inference", [])
    actual_types = [gi.get("goal_type", "?")]
    if gi.get("num_remaining", 0) > 1:
        _next(sdir, "admit.")
        actual_types.append(_goal_info(sdir).get("goal_type", "?"))
    ok = _check(name, predicted, actual_types)
    _cleanup(sdir)
    assert ok


def test_have_assign_no_branch() -> None:
    """`have h := L.` should NOT branch — just adds hypothesis."""
    name = "have h := L (no-branch)"
    sdir = Path("/tmp/claude/infer_test_have_assign")
    _setup_dice_session(sdir, "prD4")
    _next(sdir, "move=> k &m.")
    gi_before = _goal_info(sdir)
    _next(sdir, "have h := prD4.")
    gi_after = _goal_info(sdir)
    # Remaining should NOT have increased
    before_n = gi_before.get("num_remaining", 0) or 0
    after_n = gi_after.get("num_remaining", 0) or 0
    if after_n > before_n:
        print(f"  FAIL {name}: `have := L` increased num_remaining "
              f"({before_n} -> {after_n})")
        _cleanup(sdir)
        assert False
    predicted = gi_after.get("remaining_goals_inference", [])
    if predicted:
        print(f"  FAIL {name}: inferred {len(predicted)} subgoals but no branch expected")
        _cleanup(sdir)
        assert False
    print(f"  OK   {name}: correctly NOT classified as branching")
    _cleanup(sdir)


def _collect_actual_types(sdir: Path, n: int) -> list[str]:
    """Close subgoals one at a time (admit.) and record each subgoal's type.

    Returns a list of N strings (one per subgoal, in the order EC presents
    them). The LAST subgoal closes the proof, so we stop recording after
    N types are collected.
    """
    types = []
    gi = _goal_info(sdir)
    types.append(gi.get("goal_type", "?"))
    remaining = gi.get("num_remaining", 0) or 0
    while len(types) < n and remaining > 0:
        rc, _ = _next(sdir, "admit.")
        if rc != 0:
            break
        gi = _goal_info(sdir)
        types.append(gi.get("goal_type", "?"))
        remaining = gi.get("num_remaining", 0) or 0
    return types


def test_seq_K() -> None:
    """`seq K : post.` on hoare should produce 2 hoare subgoals."""
    name = "seq K : post (hoare)"
    sdir = Path("/tmp/claude/infer_test_seq")
    _setup_fixture_session(sdir, "test_seq")
    # seq requires the procedure body to be inlined first
    _next(sdir, "proc.")
    _next(sdir, "seq 1 : (M.x = 1).")
    gi = _goal_info(sdir)
    predicted = gi.get("remaining_goals_inference", [])
    actual_types = _collect_actual_types(sdir, max(len(predicted), gi.get("num_remaining", 0)))
    ok = _check(name, predicted, actual_types)
    _cleanup(sdir)
    assert ok


def test_if_branch() -> None:
    """`if => //.` on hoare produces 2 branch subgoals."""
    name = "if => // (2 branches)"
    sdir = Path("/tmp/claude/infer_test_if")
    _setup_fixture_session(sdir, "test_if")
    _next(sdir, "proc.")
    _next(sdir, "if.")
    gi = _goal_info(sdir)
    predicted = gi.get("remaining_goals_inference", [])
    actual_types = _collect_actual_types(sdir, max(len(predicted), gi.get("num_remaining", 0)))
    ok = _check(name, predicted, actual_types)
    _cleanup(sdir)
    assert ok


def test_while_loop() -> None:
    """`while (I)` on hoare produces body + exit subgoals."""
    name = "while (I) (hoare)"
    sdir = Path("/tmp/claude/infer_test_while")
    _setup_fixture_session(sdir, "test_while")
    _next(sdir, "proc.")
    _next(sdir, "wp.")
    _next(sdir, "while (0 <= i <= 10).")
    gi = _goal_info(sdir)
    predicted = gi.get("remaining_goals_inference", [])
    actual_types = _collect_actual_types(sdir, max(len(predicted), gi.get("num_remaining", 0)))
    ok = _check(name, predicted, actual_types)
    _cleanup(sdir)
    assert ok


def test_call_pRHL() -> None:
    """`call (_: ={Inv})` on pRHL produces oracle eq + sidecondition subgoals."""
    name = "call (_: Inv) (pRHL)"
    sdir = Path("/tmp/claude/infer_test_call")
    _setup_fixture_session(sdir, "test_call")
    # proc opens the pRHL goal; call with invariant branches into oracle
    # equivalence (inherits pRHL) + sidecondition (ambient).
    _next(sdir, "proc.")
    _next(sdir, "call (_: ={Oracle.y}).")
    gi = _goal_info(sdir)
    predicted = gi.get("remaining_goals_inference", [])
    actual_types = _collect_actual_types(sdir, max(len(predicted), gi.get("num_remaining", 0)))
    ok = _check(name, predicted, actual_types)
    _cleanup(sdir)
    assert ok


def test_conseq_narrow() -> None:
    """`conseq (_: pre ==> new_post).` produces 2 subgoals."""
    name = "conseq (_: ...) on hoare"
    sdir = Path("/tmp/claude/infer_test_conseq")
    _setup_fixture_session(sdir, "test_conseq")
    _next(sdir, "proc.")
    # Without `=> //` so the trivial sidecondition isn't auto-discharged.
    # New post `true` is weaker than `res = 2`, so we get two subgoals:
    # (1) main hoare under new pre/post, (2) ambient (res=2 ==> true).
    _next(sdir, "conseq (_: true ==> true).")
    gi = _goal_info(sdir)
    predicted = gi.get("remaining_goals_inference", [])
    actual_types = _collect_actual_types(sdir, max(len(predicted), gi.get("num_remaining", 0)))
    ok = _check(name, predicted, actual_types)
    _cleanup(sdir)
    assert ok


if __name__ == "__main__":
    tests = {
        "have_rewrite": test_have_rewrite,
        "have_claim_ambient": test_have_claim_ambient,
        "have_assign_no_branch": test_have_assign_no_branch,
        "seq_K": test_seq_K,
        "if_branch": test_if_branch,
        "while_loop": test_while_loop,
        "conseq_narrow": test_conseq_narrow,
        "call_pRHL": test_call_pRHL,
    }
    results = {}
    for name, test in tests.items():
        try:
            test()
        except AssertionError:
            results[name] = False
        else:
            results[name] = True
    n_pass = sum(1 for v in results.values() if v)
    print(f"\n{n_pass}/{len(results)} patterns validated")
    sys.exit(0 if n_pass == len(results) else 1)
