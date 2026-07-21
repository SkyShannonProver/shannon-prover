from __future__ import annotations

import sys
from pathlib import Path


import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_hook_phases import PivotStrategyPhase  # type: ignore  # noqa: E402
from core.easycrypt.session_hooks import DaemonHandle  # type: ignore  # noqa: E402


def _typed_candidate(chain, *, lemma="GenericBridge.pr_eq",
                     adapter="G1") -> dict:
    """A ProofIR-typed bridge candidate, the only candidate shape
    bridge_options now consumes (the regex compiler has been retired)."""
    return {
        "kind": "pr_rewrite",
        "producer": "proofir_typed_bridge_frontend",
        "semantic_objective": "Apply a type-matched Pr bridge rewrite.",
        "bridge_lemma": lemma,
        "base_lemma": lemma.split(".")[-1],
        "bindings": {
            "adapter_module": adapter,
            "lhs_game": "G(Concrete)",
            "rhs_game": "G(Ideal)",
        },
        "chain": list(chain),
        "intermediate_equality": {},
        "source": "proof_ir_typed_bridge_frontend",
    }


def _bridge_phase_with_typed_candidates(session, candidates):
    """Build a PivotStrategyPhase whose typed-bridge source is injected, so
    the verification/rendering path can be exercised without a real ProofIR
    build or EasyCrypt daemon."""
    phase = PivotStrategyPhase(session)
    phase._proof_ir_pr_bridge_candidates = lambda _raw_goal: list(candidates)
    return phase


def test_bridge_options_returns_verified_manager_intent(tmp_path) -> None:
    class FakeSession:
        history = tmp_path / "history.ec"

        def _load_narrative(self):
            return {}

        def _get_daemon_meta(self):
            return "", "step1"

    class FakeCli:
        def try_tactic(self, session_id, tactic):
            return {"accepted": "GenericBridge.pr_eq I0 G1 &m" in tactic}

        def batch_try(self, session_id, tactics):
            return [self.try_tactic(session_id, t) for t in tactics]

        def try_chain(self, session_id, chain):
            joined = " ".join(chain)
            return {"accepted": "GenericBridge.pr_eq I0 G1 &m" in joined}

    class FakeDbe:
        _session_id = "S"

    raw_goal = (
        "Pr[G(Concrete).main() @ &m : res] = "
        "Pr[D(A, Ideal).main() @ &m : res]"
    )

    phase = _bridge_phase_with_typed_candidates(
        FakeSession(),
        [_typed_candidate(["rewrite (GenericBridge.pr_eq I0 G1 &m)."])],
    )
    result = phase._try_bridge_suggest(
        raw_goal,
        DaemonHandle(cli=FakeCli(), dbe=FakeDbe()),
    )

    assert result is not None
    rec = result.recommendations[0]
    assert rec["action_type"] == "runnable_tactic"
    assert rec["metadata"]["submit"]["intent"] == "commit_tactic"
    assert rec["producer"] == "proofir_typed_bridge_frontend"
    assert rec["metadata"]["bindings"]["adapter_module"] == "G1"
    assert "-chain" not in rec["action"]


def test_bridge_options_reports_unverified_candidates(tmp_path) -> None:
    class FakeSession:
        history = tmp_path / "history.ec"

        def _load_narrative(self):
            return {}

        def _get_daemon_meta(self):
            return "", "step1"

    class RejectingCli:
        def try_tactic(self, session_id, tactic):
            return {
                "accepted": False,
                "error": {"kind": "rejected", "message": "sync failed"},
            }

        def batch_try(self, session_id, tactics):
            return [self.try_tactic(session_id, t) for t in tactics]

        def try_chain(self, session_id, chain):
            return {
                "accepted": False,
                "error": {"kind": "replay_failed", "message": "sync failed"},
            }

    class FakeDbe:
        _session_id = "S"

    raw_goal = (
        "Pr[G(Concrete).main() @ &m : res] = "
        "Pr[D(A, Ideal).main() @ &m : res]"
    )

    phase = _bridge_phase_with_typed_candidates(
        FakeSession(),
        [_typed_candidate(["rewrite (GenericBridge.pr_eq I0 G1 &m)."])],
    )
    result = phase._try_bridge_suggest(
        raw_goal,
        DaemonHandle(cli=RejectingCli(), dbe=FakeDbe()),
    )

    assert result is not None
    assert result.recommendations == []
    assert result.errors[0]["code"] == "bridge_options.no_verified_route"
    assert result.evidence["context"][0]["candidate_count"] > 0
    assert any(
        item["accepted"] is False and item.get("error_message") == "sync failed"
        for item in result.evidence["preflight"]
    )


def test_proofir_typed_bridge_candidates_are_family_general() -> None:
    """The ProofIR typed-bridge adapter must produce runnable commit_tactic
    chains for any game family (not just the ChaChaPoly regex shape), reading
    only ProofIR's typed handles -- no game-family token hardcodes."""
    handles = {
        "pr_typed_bridge_frontend": {
            "instantiated_rewrites": [
                {
                    "name": "pr_CTXT_IDEAL",
                    "lemma": "pr_CTXT_IDEAL",
                    "edge_kind": "pr_rewrite",
                    "adapter_module": "AdpCTXT",
                    "action_hint": (
                        "rewrite pr_CTXT_IDEAL.  (* instantiate distinguisher "
                        "slot with AdpCTXT *)"
                    ),
                    "reason": "Instantiate generic Pr rewrite pr_CTXT_IDEAL.",
                },
            ],
            "wrapper_bridges": [
                {
                    "name": "bridge_ctxt",
                    "edge_kind": "synthetic_bridge",
                    "lhs_game": "CTXT_game_A_Wrap",
                    "rhs_game": "CTXT_game_A_Ideal",
                    "source_pr": "Pr[CTXT_game(A, Wrap(M)).main() @ &m : res]",
                    "target_pr": "Pr[CTXT_game(A, Ideal(M)).main() @ &m : res]",
                    "tactic": (
                        "have -> : Pr[CTXT_game(A, Wrap(M)).main() @ &m : res] = "
                        "Pr[CTXT_game(A, Ideal(M)).main() @ &m : res] "
                        "by byequiv => //; proc; inline *; sim."
                    ),
                    "action_hint": "",
                    "bridge_lemma": "",
                },
                {
                    "name": "structural_only",
                    "edge_kind": "synthetic_bridge",
                    "tactic": "",
                    "action_hint": "Pr structural bridge: G_a -> G_b",
                },
            ],
        },
    }

    candidates = PivotStrategyPhase._typed_bridge_candidates_from_handles(handles)
    chains = [" ".join(c["chain"]) for c in candidates]

    # the trailing (* ... *) annotation is stripped from the instantiated rewrite
    assert "rewrite pr_CTXT_IDEAL." in chains
    # the wrapper normalization bridge is surfaced as a runnable chain
    assert any(ch.startswith("have -> :") and ch.endswith("sim.") for ch in chains)
    # the non-runnable descriptive "Pr structural bridge: ..." entry is dropped
    assert all("structural bridge" not in ch.lower() for ch in chains)
    # family-general: no ChaChaPoly-specific tokens are required or injected
    assert all(
        "CCA_game" not in ch and "RealOrcls" not in ch and "Mem.k" not in ch
        for ch in chains
    )
    # every candidate is tagged as coming from the typed ProofIR frontend
    assert candidates and all(
        c["producer"] == "proofir_typed_bridge_frontend"
        and c["source"] == "proof_ir_typed_bridge_frontend"
        for c in candidates
    )


# ── static endpoint pre-filter (no daemon) ───────────────────────────────────

def test_bridge_static_filter_drops_off_goal_keeps_in_goal_and_unparseable():
    """Static endpoint pre-filter: a bridge whose Pr endpoints match a game in
    the goal is kept; one whose endpoints are disjoint from the goal is dropped
    WITHOUT a probe; a candidate whose endpoints can't be parsed is KEPT (safety
    — never drop on uncertainty). Family-general (synthetic names)."""
    goal = ("Pr[Gc(A, Real).main() @ &m : res] = "
            "Pr[Gc(A, Ideal).main() @ &m : res]")
    in_goal = {
        "bridge_lemma": "L.in_goal", "chain": ["have -> : p by t."],
        "intermediate_equality": {
            "from": "Pr[Gc(A, Real).main() @ &m : res]",
            "to": "Pr[Gc(A, Mid).main() @ &m : res]"},
    }
    off_goal = {
        "bridge_lemma": "L.off", "chain": ["have -> : q by t."],
        "intermediate_equality": {
            "from": "Pr[Other(A, Foo).main() @ &m : res]",
            "to": "Pr[Other(A, Bar).main() @ &m : res]"},
    }
    unparseable = {
        "bridge_lemma": "L.unp", "chain": ["have -> : r by t."],
        "intermediate_equality": {},
    }
    kept, dropped = PivotStrategyPhase._bridge_candidates_in_goal(
        [in_goal, off_goal, unparseable], goal)
    assert {c["bridge_lemma"] for c in kept} == {"L.in_goal", "L.unp"}
    assert dropped == 1


def test_bridge_static_filter_keeps_all_when_goal_has_no_pr_keys():
    """No parseable goal games -> cannot scope-filter -> keep everything."""
    cand = {"bridge_lemma": "L", "chain": ["t."],
            "intermediate_equality": {"from": "Pr[X.main() @ &m : res]"}}
    kept, dropped = PivotStrategyPhase._bridge_candidates_in_goal([cand], "")
    assert kept == [cand] and dropped == 0


# ── glob: identify the called adversary statically (drop its always-rejected glob) ─

def test_called_adversary_roots_reads_glob_and_call_statement():
    """The callee is read from both `(glob A)` in the call-rule precondition
    (robust to the two-column program layout) and the `x <@ A(...)` statement."""
    goal = ("pre = (glob A){2} = (glob A){m} /\\ (glob A){1} = (glob A){m}\n"
            "b1 <@\n    A(BNR(CPA_CCA_Orcls(EncRnd))).main()\n")
    assert PivotStrategyPhase._called_adversary_roots(goal) == {"A"}


def test_called_adversary_roots_empty_without_a_call():
    assert PivotStrategyPhase._called_adversary_roots("x = y /\\ a < b") == set()


# ── rewrite: drop op-unfold candidates whose operator is absent from the goal ──

def test_rewrite_collect_drops_off_goal_op_unfolds(tmp_path) -> None:
    """A `rewrite /OP.` is a no-op (and a wasted probe) unless OP occurs in the
    goal — drop it statically. File lemmas are still collected. Synthetic
    source, family-general."""
    src = tmp_path / "m.ec"
    src.write_text(
        "op foo (x : int) = x + 1.\n"
        "op bar (y : int) = y * 2.\n"
        "lemma helper : foo 0 = 1.\n",
        encoding="utf-8")

    class FakeSession:
        context_file = str(src)

        def _load_narrative(self):
            return {}

        def _get_daemon_meta(self):
            return str(src), "lem"

    phase = PivotStrategyPhase(FakeSession())
    cands = phase._collect_rewrite_candidates("h : foo a = b /\\ x = y")
    ops = [t for k, t in cands if k == "file-op-unfold"]
    assert "rewrite /foo." in ops          # foo occurs in the goal -> kept
    assert "rewrite /bar." not in ops      # bar absent from the goal -> dropped
    assert ("file-lemma", "rewrite helper.") in cands   # lemmas still collected


# ── call-site: carry unresolved-slot info so the producer can drop fail-probes ─

def test_call_site_candidate_tactics_carry_unresolved_slots():
    """A template with unresolved non-value (module/proof) slots is tagged so the
    producer drops it (a bare `call` can't infer those — a guaranteed failure)."""
    templates = [
        {"symbol": "L.ok", "status": "direct_named_call",
         "direct_ecall_template": "call L.ok.", "unresolved_non_value_slots": []},
        {"symbol": "L.needs_mod", "status": "candidate_named_call",
         "tactic_shape": "call L.needs_mod.",
         "unresolved_non_value_slots": ["M : Oracle"]},
    ]
    by_sym = {c["symbol"]: c
              for c in PivotStrategyPhase._call_site_candidate_tactics(templates)}
    assert by_sym["L.ok"]["unresolved_slots"] == []
    assert by_sym["L.needs_mod"]["unresolved_slots"] == ["M : Oracle"]


# --- named-scan fallback at the typed-frontend empty exits (pr_bridge_routes routing) ---
# The typed frontend can't template wrapper-to-wrapper Pr=Pr bridges, so when it yields
# nothing the panel must fall back to the SAME named scan goal-info uses for
# pr_rewrite_candidates — surfaced as CONTEXT (clearly unverified), never as a runnable
# recommendation. The scan itself is covered by the goal-info channel; here we stub it and
# assert the WIRING (text + context, not recommendations) at the empty exits.
class _FakeBridgeSession:
    def __init__(self, history):
        self.history = history

    def _load_narrative(self):
        return {}

    def _get_daemon_meta(self):
        return "", "step1"


class _RejectingCli:
    def try_tactic(self, sid, tactic):
        return {"accepted": False, "error": {"kind": "rejected", "message": "no"}}

    def batch_try(self, sid, tactics):
        return [self.try_tactic(sid, t) for t in tactics]

    def try_chain(self, sid, chain):
        return {"accepted": False, "error": {"kind": "replay_failed", "message": "no"}}


class _FakeDbe:
    _session_id = "S"


def _stub_named_fallback(phase, name="pr_coll_coll2"):
    phase._scan_named_bridge_fallback = lambda _g: [
        {"name": name, "file": "Coll.ec",
         "availability": "session_local", "matched_by": "name_and_endpoint"},
    ]


_PR_EQ_GOAL = "Pr[Coll(H,A).main(b) @ &m : res] = Pr[Coll2(H,A).main(b) @ &m : res]"


def _assert_named_fallback_surfaced(result):
    assert result is not None
    assert result.recommendations == []                 # never promoted to a runnable rec
    assert "pr_coll_coll2" in result.text                # surfaced by name
    assert "NOT daemon-verified" in result.text          # clearly labelled unverified
    scan = [e for e in result.evidence["context"]
            if e.get("producer") == "scan_pr_bridge_lemmas"]
    assert scan and any(c["name"] == "pr_coll_coll2" for c in scan[0]["candidates"])


def test_no_verified_route_surfaces_named_scan_fallback_as_context(tmp_path) -> None:
    phase = _bridge_phase_with_typed_candidates(
        _FakeBridgeSession(tmp_path / "history.ec"),
        [_typed_candidate(["rewrite (GenericBridge.pr_eq I0 G1 &m)."])],
    )
    _stub_named_fallback(phase)
    result = phase._try_bridge_suggest(
        _PR_EQ_GOAL, DaemonHandle(cli=_RejectingCli(), dbe=_FakeDbe()))
    assert result.errors[0]["code"] == "bridge_options.no_verified_route"
    _assert_named_fallback_surfaced(result)

def test_no_candidates_exit_also_surfaces_named_scan_fallback(tmp_path) -> None:
    # the coverage-gap case: typed frontend produces nothing (wrapper-to-wrapper Pr=Pr)
    phase = _bridge_phase_with_typed_candidates(
        _FakeBridgeSession(tmp_path / "history.ec"), [])
    _stub_named_fallback(phase)
    result = phase._try_bridge_suggest(
        _PR_EQ_GOAL, DaemonHandle(cli=_RejectingCli(), dbe=_FakeDbe()))
    assert any(n.get("code") == "bridge_options.no_candidates" for n in (result.notes or []))
    _assert_named_fallback_surfaced(result)
