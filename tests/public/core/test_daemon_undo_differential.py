"""F2 equivalence: rewinding with EasyCrypt's ``undo`` vs restart+replay.

Real EasyCrypt, real ``session_cli`` subprocesses and a real daemon, driven
through ``ReplSessionManager`` exactly as a proof node drives them. Skipped
without the repository-managed toolchain.

For each proof the undo arm commits the original proof script forward and
records the state after every kept command: committed history, the managed
goal view the agent sees (status, goal identity, goal text) and
``current.out``. Those forward states are what restart+replay reaches by
construction (it is ``-start`` plus the same commits); the reference arm
checks that claim by running the real restart+replay path at several depths.
The undo arm then:

* rewinds to many depths and must land exactly on the forward state, with
  one ``undo`` action and no replay steps, and the next commits from there
  must reproduce the forward states (so the restored EasyCrypt scope behaves
  identically, not just prints identically);
* restores and amends, which undo to the common prefix and replay only the
  differing suffix, and must match the reference arm's restart+replay;
* rejects a tactic, rejects a transaction after it ran a sentence, and
  reverts a no-op, each of which must leave the daemon session in place at
  the pre-commit state; and
* commits ``pragma`` transactions, for which rewinds must fall back to
  restart+replay (``undo`` does not restore what a pragma changes).

``current.out`` is compared with prompt lines removed: the prompt carries
EasyCrypt's undo level, which a ``locate`` re-print can shift without any
state change. The prompt *mode* (``check``/``weakcheck``) is compared.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]

from core.easycrypt.committed_history import read_committed_transactions  # noqa: E402
from core.easycrypt.ec_env import get_ec_env  # noqa: E402
from core.easycrypt.ec_prompt import PROMPT_LINE_RE, PROMPT_RE  # noqa: E402
from core.easycrypt.proof_text import split_ec_commands, strip_comments  # noqa: E402
from workflow.proof_management.protocol_repair import AgentIntent  # noqa: E402
from workflow.proof_management.repl_session import ReplSessionManager  # noqa: E402

try:
    _MANAGED_EC_AVAILABLE = shutil.which(
        "easycrypt", path=get_ec_env().get("PATH")
    ) is not None
except RuntimeError:
    _MANAGED_EC_AVAILABLE = False

pytestmark = [pytest.mark.easycrypt, pytest.mark.skipif(
    not _MANAGED_EC_AVAILABLE,
    reason="repository-managed EasyCrypt is unavailable",
)]

THEORIES = ROOT / "easycrypt-src" / "theories"


@pytest.fixture(scope="module", autouse=True)
def _private_why3_route():
    # A route nobody serves: EasyCrypt then runs its provers itself instead
    # of joining a why3server another run may own. (The daemon socket is
    # already module-private, see conftest._ec_daemon_hygiene.)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("WHY3EC_SOCKET", f"/tmp/f2w_{uuid.uuid4().hex[:10]}.sock")
        yield


def proof_script(relative: str, lemma: str, *, with_qed: bool = False) -> list[str]:
    """The proof body of ``lemma`` as single-command transactions."""
    text = (ROOT / relative).read_text(encoding="utf-8")
    match = re.search(
        rf"(?m)^\s*(?:local\s+)?(?:lemma|equiv|hoare|phoare)\s+{re.escape(lemma)}\b",
        text,
    )
    assert match, lemma
    start = text.index("proof.", match.end()) + len("proof.")
    end = text.index("qed.", start)
    commands = [
        " ".join(strip_comments(command).split())
        for command in split_ec_commands(text[start:end])
    ]
    commands = [command for command in commands if command]
    return commands + (["qed."] if with_qed else [])


def _mode(text: str) -> str:
    modes = [match.group(2) for match in PROMPT_RE.finditer(text)]
    return modes[-1] if modes else ""


@dataclass(frozen=True)
class State:
    history: tuple[str, ...]
    view: str
    current: str
    mode: str

    @property
    def summary(self) -> str:
        view = json.loads(self.view)
        status = view.get("proof_status", {})
        return (
            f"{len(self.history)} cmds status={status.get('status')} "
            f"goal={str(status.get('goal_hash'))[:10]} mode={self.mode}"
        )


class Arm:
    """One proof node's manager-owned session."""

    def __init__(self, root: Path, tag: str, source: str, lemma: str) -> None:
        self.repl = ReplSessionManager(
            file_path=str(ROOT / source),
            lemma_name=lemma,
            include_dir=str(THEORIES),
            session_tag=tag,
            node_id=f"Tree-{tag}",
            project_root=ROOT,
        )
        self.repl.session_dir = str(root / tag)
        self.dir = root / tag
        self.actions: list[dict[str, Any]] = []

    def observe(self, snapshot) -> State:
        current = (self.dir / "current.out").read_text(encoding="utf-8")
        return State(
            history=tuple(self.repl.committed_history()),
            view=json.dumps(snapshot.raw_workspace_view, sort_keys=True),
            current=PROMPT_LINE_RE.sub("", current).strip(),
            mode=_mode(current),
        )

    def _done(self, result) -> State:
        snapshot, actions = result
        self.actions = actions
        return self.observe(snapshot)

    def start(self) -> State:
        return self._done(self.repl.start())

    def commit(self, tactic: str) -> State:
        return self._done(self.repl.handle_intent(
            AgentIntent(intent="commit_tactic", payload={"tactic": tactic})
        ))

    def undo_last(self) -> State:
        return self._done(self.repl.handle_intent(AgentIntent(intent="undo_last_step")))

    def rewind(self, keep: int) -> State:
        return self._done(self.repl.rewind_before_tactic(keep + 1))

    def restore(self, tactics: list[str]) -> State:
        return self._done(self.repl.restore_committed_tactics(list(tactics)))

    def amend(self, edited: list[str]) -> State:
        return self._done(self.repl.restart_with_edited_prefix(list(edited)))

    def restart_replay(self, prefix: list[str], **kwargs: Any) -> State:
        """The canonical restart+replay path, as the manager ran it before F2."""
        with self.repl._lock:
            return self._done(self.repl._start_locked(
                replay_prefix=list(prefix),
                label="restart_reference",
                force_restart=True,
                **kwargs,
            ))

    def labels(self) -> list[str]:
        return [str(action.get("label")) for action in self.actions]

    def mode(self) -> str:
        return _mode((self.dir / "current.out").read_text(encoding="utf-8"))

    def daemon_state(self) -> dict[str, Any]:
        path = self.dir / "daemon_state.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def events(self, kind: str) -> list[dict[str, Any]]:
        lines = (self.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        return [
            event.get("payload", {})
            for event in map(json.loads, lines)
            if event.get("type") == kind
        ]

    def close(self) -> None:
        self.repl.close()


def forward(arm: Arm, script: list[str]) -> tuple[list[State], list[str]]:
    """Commit ``script``; return the state after each kept command and the
    kept commands. A command the session reverts as a no-op is not kept
    (restart+replay would revert it too), and its state equals the last."""
    states = [arm.start()]
    kept: list[str] = []
    for tactic in script:
        state = arm.commit(tactic)
        if len(state.history) == len(states) - 1:
            assert arm.actions[0]["outcome_kind"] == "no_progress", tactic
            assert_same(state, states[-1], f"reverted {tactic!r}", view=False)
            assert_daemon_session_kept(arm)
            continue
        assert len(state.history) == len(states), tactic
        kept.append(tactic)
        states.append(state)
    return states, kept


def _without_prompt_lines(view_json: str) -> dict[str, Any]:
    view = json.loads(view_json)
    goal = view.get("current_goal") or {}
    if goal:
        lines = [line for line in goal["lines"] if not PROMPT_RE.fullmatch(line.strip())]
        view["current_goal"] = {"lines": lines}
    return view


def assert_same(
    actual: State,
    expected: State,
    what: str,
    *,
    view: bool = True,
    batch_reference: bool = False,
) -> None:
    """Equal history, prompt mode, goal output and managed view.

    ``batch_reference``: the expected state was written by a batch replay
    (a session at depth 0 has replayed nothing on the daemon). Batch output
    puts the ``[N|mode]>`` line before the goal, the daemon after it, and the
    view's goal lines keep a trailing prompt line. Every daemon commit has
    that layout; the goal text and canonical goal hash are the same.
    """
    assert actual.history == expected.history, what
    assert actual.mode == expected.mode, what
    assert actual.current == expected.current, what
    if not view:
        return
    if batch_reference:
        assert _without_prompt_lines(actual.view) == _without_prompt_lines(
            expected.view
        ), f"{what}: {actual.summary} != {expected.summary}"
        return
    assert actual.view == expected.view, (
        f"{what}: {actual.summary} != {expected.summary}"
    )


def assert_rewound_in_place(arm: Arm) -> None:
    labels = arm.labels()
    assert labels[-1] == "managed_goal_view", labels
    assert "daemon_undo_fallback" not in labels, arm.actions[0]
    assert not [label for label in labels if label.startswith("replay_prefix_step_")]
    undone = arm.events("tactic.undone")[-1]
    assert undone["backend"] == "daemon_undo", undone


def assert_fell_back(arm: Arm, reason: str) -> None:
    fallback = arm.actions[0]
    assert fallback["label"] == "daemon_undo_fallback", arm.labels()
    assert reason in fallback["daemon_undo"]["reason"], fallback["daemon_undo"]
    assert fallback["needs_attention"] is False
    assert "-start" in arm.actions[1]["argv"]


def assert_daemon_session_kept(arm: Arm) -> None:
    """The daemon still holds exactly the journal: no reopen is pending."""
    state = arm.daemon_state()
    assert state, "daemon session was dropped"
    assert state["committed_count"] == len(read_committed_transactions(arm.dir))


# Accepted on any open goal, and it changes the goal (one more hypothesis).
BRANCH_TACTIC = "have f2_branch : true by trivial."


def _replay_markers(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in action.items() if key.startswith("replay_")}
        for action in actions
        if action.get("label") in {
            "replay_prefix_stopped_at_divergence",
            "replay_prefix_divergence",
        }
    ]


@dataclass(frozen=True)
class Case:
    name: str
    source: str
    lemma: str
    with_qed: bool
    rewind_points: tuple[int, ...]
    restart_points: tuple[int, ...]
    amend_index: int
    amend_tactic: str
    # The fixture is a goal without a proof; its script is given here.
    script: tuple[str, ...] = ()
    limit: int | None = None

    def proof(self) -> list[str]:
        if self.script:
            return list(self.script)
        script = proof_script(self.source, self.lemma, with_qed=self.with_qed)
        return script if self.limit is None else script[: self.limit]


CASES = [
    # tests/fixtures: a synthetic intro chain closed by trivial + qed.
    Case(
        name="fixture_intro_chain",
        source="tests/public/fixtures/native_semantics/deep_goal.ec",
        lemma="native_state_deep_goal",
        with_qed=True,
        rewind_points=(11, 7, 3, 0, 12),
        restart_points=(0, 6, 12),
        amend_index=2,
        amend_tactic="move=> second.",
        script=tuple(
            [f"move=> h{i}." for i in range(11)] + ["trivial.", "qed."]
        ),
    ),
    # phoare: byphoare, while invariant, case split, smt. The first 25
    # commands; step 26's smt is beyond the repository's prover set.
    Case(
        name="pir_correct_phoare",
        source="eval/examples/PIR.ec",
        lemma="PIR_correct",
        with_qed=False,
        rewind_points=(21, 18, 13, 8, 4, 1, 0),
        restart_points=(0, 4, 13, 21),
        amend_index=3,
        amend_tactic="proc; inline *; wp.",
        limit=25,
    ),
    # pRHL: byequiv, swaps, rnd with a bijection, call, ring/smt, then qed.
    Case(
        name="hashed_elgamal_es0_gb_equiv",
        source="eval/examples/hashed_elgamal_std.ec",
        lemma="es0_Gb",
        with_qed=True,
        rewind_points=(33, 27, 20, 14, 9, 5, 2, 0, 34),
        restart_points=(5, 20, 34),
        amend_index=5,
        amend_tactic="swap{2} 7 -2.",
    ),
    # pRHL up-to-bad: byequiv with a bad event, call with an invariant,
    # inline/swap/rnd. The first 13 commands (step 14's smt as above).
    Case(
        name="prg_plog_psample_upto_bad",
        source="eval/examples/PRG.ec",
        lemma="Plog_Psample",
        with_qed=False,
        rewind_points=(12, 9, 6, 3, 0),
        restart_points=(3, 12),
        amend_index=6,
        amend_tactic="swap{1} 3 -1.",
        limit=13,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_rewind_restore_amend_match_restart_replay(case: Case, tmp_path: Path) -> None:
    undo = Arm(tmp_path, "undo", case.source, case.lemma)
    reference = Arm(tmp_path, "ref", case.source, case.lemma)
    try:
        states, script = forward(undo, case.proof())
        n = len(script)
        assert max(case.rewind_points + case.restart_points) <= n
        assert_daemon_session_kept(undo)

        # The forward states are restart+replay states: check at depths.
        for depth in case.restart_points:
            assert_same(
                reference.restart_replay(script[:depth]),
                states[depth],
                f"restart+replay of {depth} commands",
            )

        # Rewind to many depths; after each, the next commits must behave
        # exactly as they did on the forward pass.
        held = n
        for keep in case.rewind_points:
            while held <= keep:
                assert_same(undo.commit(script[held]), states[held + 1], "advance")
                held += 1
            rewound = undo.rewind(keep)
            if keep and "No more goals" in states[keep].current:
                # A goals-closed target needs the replayed close events.
                assert_fell_back(undo, "no_open_goal")
            else:
                assert_rewound_in_place(undo)
            assert_same(
                rewound, states[keep], f"rewind {held}->{keep}",
                batch_reference=keep == 0,
            )
            held = keep
            for step in range(keep, min(keep + 2, n)):
                assert_same(
                    undo.commit(script[step]), states[step + 1],
                    f"commit {step + 1} after rewind to {keep}",
                )
                held = step + 1
            assert_daemon_session_kept(undo)

        # Restore forward from a rewound state: only the suffix is replayed.
        undo.rewind(2)
        restored = undo.restore(script[: n - 1])
        assert undo.labels()[0] == "restore_pre_rewind"
        assert undo.actions[0]["replay_steps_avoided"] == 2
        replayed = [l for l in undo.labels() if l.startswith("replay_prefix_step_")]
        assert replayed == [f"replay_prefix_step_{i}" for i in range(3, n)]
        assert_same(restored, states[n - 1], "restore to n-1")

        # Restore across a divergent branch: undo to the common prefix, then
        # replay only the rest of the target.
        branch_at = case.amend_index - 1
        undo.rewind(branch_at)
        branch = undo.commit(BRANCH_TACTIC)
        assert branch.history == states[branch_at].history + (BRANCH_TACTIC,)
        restored = undo.restore(script[: branch_at + 3])
        assert undo.labels()[0] == "restore_pre_rewind"
        assert "--keep-commands" in undo.actions[0]["argv"]
        assert sum(l.startswith("replay_prefix_step_") for l in undo.labels()) == 3
        assert_same(restored, states[branch_at + 3], "restore across a branch")

        # Amend: undo to before the amended step, replay the rest, stopping at
        # the first step the edit invalidates. Compare with restart+replay.
        undo.restore(script)
        edited = list(script)
        edited[case.amend_index - 1] = case.amend_tactic
        amended = undo.amend(edited)
        assert undo.labels()[0] == "restart_replay_edit"
        assert "--keep-commands" in undo.actions[0]["argv"]
        undo_markers = _replay_markers(undo.actions)
        expected = reference.restart_replay(edited, stop_at_first_drop=True)
        assert_same(amended, expected, "amend")
        assert undo_markers == _replay_markers(reference.actions)
    finally:
        undo.close()
        reference.close()


def test_rejections_and_noops_keep_the_daemon_session(tmp_path: Path) -> None:
    source, lemma = "eval/examples/PIR.ec", "PIR_correct"
    script = proof_script(source, lemma, with_qed=True)
    arm = Arm(tmp_path, "rej", source, lemma)
    try:
        states, kept = forward(arm, script[:6])
        assert kept == script[:6]
        undo_before = len(arm.events("tactic.undone"))
        for bad, outcome in (
            ("bogus_tactic_f2.", "rejected"),               # nothing ran
            (f"{script[6]} bogus_tactic_f2.", "rejected"),  # a sentence ran first
            ("idtac.", "no_progress"),                       # accepted no-op
        ):
            state = arm.commit(bad)
            assert arm.actions[0]["outcome_kind"] == outcome, bad
            # The view reports the rejection itself (status), so only the
            # proof state is compared here.
            assert_same(state, states[6], f"after {bad!r}", view=False)
            assert json.loads(state.view)["proof_status"]["goal_hash"] == (
                json.loads(states[6].view)["proof_status"]["goal_hash"]
            )
            assert_daemon_session_kept(arm)
        # The next commit runs on the kept daemon session.
        next_state = arm.commit(script[6])
        routing = arm.events("ec.routing")[-1]
        assert routing["reason"] == "daemon_accept", routing
        arm_ref = Arm(tmp_path, "rej_ref", source, lemma)
        try:
            assert_same(next_state, arm_ref.restart_replay(script[:7]), "after rejections")
        finally:
            arm_ref.close()
        # undo_last_step also undoes the daemon instead of a batch replay.
        state = arm.undo_last()
        assert arm.events("tactic.undone")[-1]["backend"] == "daemon_undo"
        assert len(arm.events("tactic.undone")) == undo_before + 1
        assert_same(state, states[6], "undo_last_step")
        assert_daemon_session_kept(arm)
        assert_same(arm.commit(script[6]), next_state, "commit after undo_last_step")
    finally:
        arm.close()


@pytest.mark.parametrize("pragma", ["pragma Proofs:weak.", "pragma +PP:showtvi."])
def test_pragma_in_journal_forces_restart_replay(pragma: str, tmp_path: Path) -> None:
    source, lemma = "eval/examples/PIR.ec", "PIR_correct"
    script = proof_script(source, lemma, with_qed=True)
    arm = Arm(tmp_path, "prag", source, lemma)
    reference = Arm(tmp_path, "prag_ref", source, lemma)
    try:
        states, kept = forward(arm, script[:3])
        assert kept == script[:3]
        # One transaction: the pragma, then a real step (so it is kept).
        arm.commit(f"{pragma} {script[3]}")
        if "weak" in pragma:
            assert arm.mode() == "weakcheck"
        arm.commit(script[4])
        # The undone range holds the pragma: undo would keep its effect.
        rewound = arm.rewind(3)
        assert_fell_back(arm, "undo cannot revert")
        assert_same(rewound, states[3], "rewind across a pragma")
        assert rewound.mode == "check"
        # A pragma in the kept prefix also falls back: restart+replay
        # re-commits it on its own, where it is reverted as a no-op.
        arm.commit(f"{pragma} {script[3]}")
        arm.commit(script[4])
        arm.commit(script[5])
        kept = list(arm.repl.committed_history()[:5])
        rewound = arm.rewind(5)
        assert_fell_back(arm, "undo cannot revert")
        assert_same(rewound, reference.restart_replay(kept), "rewind keeping a pragma")
    finally:
        arm.close()
        reference.close()
