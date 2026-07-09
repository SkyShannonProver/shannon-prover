"""Validate ec_state_diff structural verdict + cosmetic-noise detection.

Exercises three canonical transitions:

  1. PROGRESS_WITH_COSMETIC_NOISE — a `rewrite -LEMMA` reduces module
     nesting depth (4 -> 3) but introduces an applied lambda
     `(fun _ r => r) (..) res`. The verdict must be
     PROGRESS_WITH_COSMETIC_NOISE and the recommendation must
     describe the structural progress so the agent has the data to
     decide rather than being told what to do.

  2. REGRESSION — a tactic that doubles the subgoal count or adds
     Pr[] terms. The verdict must be REGRESSION.

  3. NEUTRAL_OR_NO_CHANGE — identical pre/post text. The verdict must
     be NEUTRAL_OR_NO_CHANGE and `format_state_diff_block` must return
     "" so we don't spam the agent with a no-op emission.

Run: `python3 tests/test_state_diff.py`
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from core.easycrypt.analysis.ec_state_diff import (  # type: ignore  # noqa: E402
    compute_state_diff,
    format_state_diff_block,
)


# ---------------------------------------------------------------------------
# Fixtures: synthetic but realistic-shaped EC output snippets.
# ---------------------------------------------------------------------------


# Case 1: PROGRESS_WITH_COSMETIC_NOISE
# Pre  — module depth 4, single Pr[] equality.
# Post — module depth 3, beta-redex `(fun _ r => r) (..) res` introduced.
# Names are GENERIC placeholders (Wrap1/Wrap2/RO_Pair/Inner) — not project-specific.
PRE_PROGRESS = """\
Current goal

Type variables: <none>

&m: memory
----------------------------------------------------------------------
Pr[Wrap1(Wrap2(RO_Pair(Inner.RO))).run() @ &m : res] = Pr[BaseGame.main() @ &m : res]
"""

POST_PROGRESS = """\
Current goal

Type variables: <none>

&m: memory
----------------------------------------------------------------------
Pr[Wrap1(Wrap2(Inner.RO)).run() @ &m : (fun _ r => r) ((glob A), Mem.k, &m) res] = Pr[BaseGame.main() @ &m : res]
"""


# Case 2: REGRESSION
# Pre  — 1 subgoal.
# Post — 3 subgoals from a non-decomposition tactic (e.g. `apply` that
# unified too loosely and spawned speculative goals).
# 2026-04-29 root-cause rewrite: REGRESSION fires only on subgoal_count
# strictly increasing under a non-decomposition tactic. Earlier fixture
# tested "Pr[] count increased" — but that signal was the dominant
# false-positive on legitimate pRHL unfolds (proc/inline/call/wp/sp),
# so it's no longer a REGRESSION trigger.
PRE_REGRESSION = """\
Current goal

----------------------------------------------------------------------
Pr[Game.main() @ &m : res] = Pr[Game2.main() @ &m : res]
"""

POST_REGRESSION = """\
Current goal (remaining: 3)

----------------------------------------------------------------------
Pr[Game.main() @ &m : res] <= Pr[Helper.aux() @ &m : res]
"""


# Case 3: NEUTRAL — identical pre/post.
PRE_NEUTRAL = """\
Current goal

----------------------------------------------------------------------
forall x, x = x
"""

POST_NEUTRAL = PRE_NEUTRAL


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


def _check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}: {detail}")
        raise AssertionError(f"{name}: {detail}")


def test_progress_with_cosmetic_noise() -> None:
    print("[1] PROGRESS_WITH_COSMETIC_NOISE — rewrite simplifies module tree but introduces beta-redex")
    diff = compute_state_diff(
        PRE_PROGRESS, POST_PROGRESS, "rewrite -(SomeLemma _ _ _).",
    )
    pre, post = diff["pre_metrics"], diff["post_metrics"]
    _check("pre.module_depth >= post.module_depth",
           pre["module_depth_max"] >= post["module_depth_max"],
           f"pre={pre['module_depth_max']} post={post['module_depth_max']}")
    _check("module_depth strictly decreased",
           post["module_depth_max"] < pre["module_depth_max"],
           f"pre={pre['module_depth_max']} post={post['module_depth_max']}")
    _check("beta_redex detected as new noise",
           "beta_redex" in diff["cosmetic_noise"],
           f"noise={diff['cosmetic_noise']}")
    _check("verdict is PROGRESS_WITH_COSMETIC_NOISE",
           diff["verdict"] == "PROGRESS_WITH_COSMETIC_NOISE",
           f"verdict={diff['verdict']}")
    _check("recommendation describes structural progress",
           "Structural progress" in diff["recommendation"],
           f"recommendation={diff['recommendation']!r}")
    block = format_state_diff_block(diff)
    _check("formatted block emitted", bool(block.strip()), "block was empty")
    _check("formatted block has [STATE-DIFF] header",
           block.lstrip().startswith("[STATE-DIFF]"),
           f"block={block!r}")
    _check("formatted block under 12 lines",
           block.count("\n") <= 12,
           f"lines={block.count(chr(10))}")
    print()
    print("  ----- block preview -----")
    for ln in block.splitlines():
        print(f"  | {ln}")
    print("  -------------------------")
    print()


def test_subgoal_increase_is_decomposition() -> None:
    """2026-04-29 root-cause rewrite: ANY subgoal_count increase with
    a text change is treated as PROGRESS_DECOMPOSITION, regardless of
    whether the tactic name appears in a known-decomposition list. The
    earlier list-based heuristic missed `congr` / `call (_: Inv)` /
    `have h : P` / `while (I)` / compound tactics with `case` — all
    legitimate decompositions surfacing as REGRESSION. Toxic-loop "no-op
    spawned subgoals" is already caught by text_unchanged → NEUTRAL,
    so count-up + text-change = decomposition is sound."""
    print("[2] subgoal count increase → PROGRESS_DECOMPOSITION (regardless "
          "of tactic name)")
    diff = compute_state_diff(
        PRE_REGRESSION, POST_REGRESSION, "apply WrongLemma.",
    )
    pre, post = diff["pre_metrics"], diff["post_metrics"]
    _check("subgoal count strictly increased",
           post["subgoals_count"] > pre["subgoals_count"],
           f"pre={pre['subgoals_count']} post={post['subgoals_count']}")
    _check("verdict is PROGRESS_DECOMPOSITION",
           diff["verdict"] == "PROGRESS_DECOMPOSITION",
           f"verdict={diff['verdict']}")
    print()


def test_decomposition_is_not_regression() -> None:
    """Run 13 step3 step 106 motivation: `seq 1 1 : (P)` was getting
    verdict=REGRESSION purely because subgoals/quantifiers/connectives
    increased — but those increases are EXPECTED for seq. The new
    PROGRESS_DECOMPOSITION verdict surfaces that and gives a
    tactic-specific recommendation instead of suggesting -prev."""
    print("[2b] PROGRESS_DECOMPOSITION — seq/case/transitivity surfaced as "
          "PROGRESS, not REGRESSION")
    pre = "Current goal\n----\npost = res{1} = res{2}\n"
    post = ("Current goal (remaining: 2)\n----\n"
            "post = (forall a, P /\\ Q)\n")
    for tac, kind in [("seq 1 1 : (P).", "seq"),
                      ("transitivity M.proc (...).", "transitivity"),
                      ("case (b).", "case"),
                      ("split.", "split")]:
        diff = compute_state_diff(pre, post, tac)
        _check(f"  {kind}: verdict is PROGRESS_DECOMPOSITION (not REGRESSION)",
               diff["verdict"] == "PROGRESS_DECOMPOSITION",
               f"verdict={diff['verdict']}")
        _check(f"  {kind}: recommendation describes the decomposition",
               "decomposition" in diff["recommendation"].lower()
               or "structural" in diff["recommendation"].lower(),
               f"rec={diff['recommendation'][:80]!r}")
        block = format_state_diff_block(diff)
        _check(f"  {kind}: block IS emitted (not suppressed)",
               bool(block.strip()),
               "block was empty (NEUTRAL_OR_NO_CHANGE suppression?)")
    print()


def test_neutral() -> None:
    print("[3] NEUTRAL — identical pre/post text yields no informative block")
    diff = compute_state_diff(PRE_NEUTRAL, POST_NEUTRAL, "idtac.")
    _check("verdict is NEUTRAL_OR_NO_CHANGE",
           diff["verdict"] == "NEUTRAL_OR_NO_CHANGE",
           f"verdict={diff['verdict']}")
    block = format_state_diff_block(diff)
    _check("formatted block is empty (suppressed)",
           block == "",
           f"block={block!r}")
    print()


def test_progress_clean() -> None:
    """Bonus: a `rewrite` that tidies the goal without adding any noise
    should classify as PROGRESS, not PROGRESS_WITH_COSMETIC_NOISE."""
    print("[4] PROGRESS (clean) — module nesting reduced, no new noise")
    pre = """\
Current goal

----------------------------------------------------------------------
Pr[Wrap(RO_Pair(Inner.RO)).main() @ &m : res] = 0%r
"""
    post = """\
Current goal

----------------------------------------------------------------------
Pr[Wrap(Inner.RO).main() @ &m : res] = 0%r
"""
    diff = compute_state_diff(pre, post, "rewrite -SomeLemma.")
    _check("verdict is PROGRESS",
           diff["verdict"] == "PROGRESS",
           f"verdict={diff['verdict']}, "
           f"noise={diff['cosmetic_noise']}, "
           f"pre_module_depth={diff['pre_metrics']['module_depth_max']}, "
           f"post_module_depth={diff['post_metrics']['module_depth_max']}")
    _check("cosmetic_noise list is empty",
           diff["cosmetic_noise"] == [],
           f"noise={diff['cosmetic_noise']}")
    print()


def test_progress_decomposition_warns_on_progress_tactic() -> None:
    """Fix A (audit 2026-04-30, step3 Tree-0.0 stuck window 00:51-01:18):
    `progress.` from a relational ambient goal produced 13 leaves; one
    leaf needed `p0{1} = p0{2}` from outer context which progress
    stripped. Agent diagnosed the loss 8 min later but spent 15 min
    thrashing on hint search. Fix: when the decomposition tactic is
    `progress`, the recommendation must warn about hypothesis loss
    and tell the agent to prefix `move=> &1 &2 [Heq ...]` to preserve
    relational equalities BEFORE the split."""
    print("[5] PROGRESS_DECOMPOSITION on `progress.` warns about "
          "relational hypothesis loss")
    pre = ("Current goal\n----\n"
           "post = (Mem.log{1}.[k1 <- p0{1}] = Mem.log{2}.[k2 <- p0{2}] "
           "/\\ p0{1} = p0{2} /\\ rest)\n")
    post = ("Current goal (remaining: 13)\n----\n"
            "Mem.log{1}.[k1 <- p0{1}] = Mem.log{2}.[k2 <- p0{2}]\n")
    diff = compute_state_diff(pre, post, "progress.")
    _check("verdict is PROGRESS_DECOMPOSITION",
           diff["verdict"] == "PROGRESS_DECOMPOSITION",
           f"verdict={diff['verdict']}")
    rec = diff["recommendation"]
    _check("recommendation mentions `progress` by name",
           "progress" in rec.lower(),
           f"rec={rec[:120]!r}")
    _check("recommendation warns about hypothesis propagation loss",
           "propagate" in rec.lower() or "context" in rec.lower(),
           f"rec={rec[:120]!r}")
    _check("recommendation tells agent to use `move=> &1 &2 [Heq ...]`",
           "move=> &1 &2" in rec or "move => &1 &2" in rec,
           f"rec={rec[:160]!r}")
    # Trace re-read 2026-04-30: at 01:04:29 Tree-0.0 hit "unknown
    # memory: &1" by re-introducing binders that progress had already
    # consumed. Misdiagnosed as goal_type confusion, lost ~5 min.
    # Advice should warn about this second progress side-effect
    # (eager quantifier introduction) on top of the hypothesis-loss
    # warning, so agent doesn't replay the same probe pattern.
    _check("recommendation warns about `unknown memory` from re-intro",
           "unknown memory" in rec.lower(),
           f"rec={rec[:200]!r}")
    print()


def test_progress_decomposition_seq_unchanged() -> None:
    """Sanity: the new `progress` branch must NOT regress the existing
    `seq` / `case` / `transitivity` recommendation paths. Those should
    still talk about structural decomposition without any progress-
    specific warning."""
    print("[5b] non-progress decomposition branches still produce their "
          "existing recommendations (no leak from Fix A)")
    pre = "Current goal\n----\npost = res{1} = res{2}\n"
    post = ("Current goal (remaining: 2)\n----\n"
            "post = (forall a, P /\\ Q)\n")
    for tac, kind in [("seq 1 1 : (P).", "seq"),
                      ("case (b).", "case")]:
        diff = compute_state_diff(pre, post, tac)
        rec = diff["recommendation"]
        _check(f"  {kind}: recommendation does NOT contain progress warning",
               "progress" not in rec.lower(),
               f"rec leaked progress text: {rec[:80]!r}")
        _check(f"  {kind}: recommendation does NOT contain `move=> &1 &2`",
               "move=> &1 &2" not in rec and "move => &1 &2" not in rec,
               f"rec leaked move=> binder pattern: {rec[:80]!r}")
    print()


if __name__ == "__main__":
    print("=== ec_state_diff structural verdict tests ===")
    print()
    test_progress_with_cosmetic_noise()
    test_subgoal_increase_is_decomposition()
    test_decomposition_is_not_regression()
    test_neutral()
    test_progress_clean()
    test_progress_decomposition_warns_on_progress_tactic()
    test_progress_decomposition_seq_unchanged()
    print("All tests passed.")
