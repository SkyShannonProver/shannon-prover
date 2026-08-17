"""Live no-model probe for the N2b.3 probability multi-slot descriptor."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from core.easycrypt.eval_source_prep import prepare_eval_source
from workflow.proof_management.protocol_repair import AgentIntent
from workflow.proof_management.repl_session import (
    ReplSessionManager,
    session_dir_path,
)
from workflow.proof_state_compiler.input_gateway import live_compiler_input


ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILE = "eval/examples/ChaChaPoly/chacha_poly.ec"
LEMMA = "step2_1"
REPLAY_PREFIX = (
    "apply (ler_trans Pr[CCA_game(A, RealOrcls(StLSke(St))).main() "
    "@ &m : res]); first last.",
)
REJECTED_TACTIC = "apply CCA_UFCMA.CCA_CPA_UFCMA."
APPLICATION_TERM = "CCA_UFCMA.CCA_CPA_UFCMA St _ _ A A_ll &m"


def run_b24_native_descriptor_sentinel(
    root: Path = ROOT,
) -> dict[str, Any]:
    """Reach the pinned post-ler_trans state and ask only native EasyCrypt."""

    token = uuid.uuid4().hex[:12]
    tag = f"n2b3_descriptor_{token}"
    source_output = root / f".n2b3_descriptor_sources_{token}"
    original_source = root / SOURCE_FILE
    prepared = prepare_eval_source(
        source_file=original_source,
        target_lemma=LEMMA,
        output_dir=source_output,
        copy_root=original_source.parent,
        strip_proofs=True,
    )
    manager = ReplSessionManager(
        file_path=str(prepared.isolated_file),
        lemma_name=LEMMA,
        include_dir="easycrypt-src/theories",
        session_tag=tag,
        node_id=f"validation-{tag}",
        project_root=root,
    )
    session_path = session_dir_path(manager.session_dir, root)
    try:
        manager.start(replay_prefix=list(REPLAY_PREFIX))
        history_before = tuple(manager.committed_history())
        if history_before != REPLAY_PREFIX:
            raise RuntimeError("B2/B4 native probe missed the pinned boundary")
        native_state_request_id = f"n2b3-state-{uuid.uuid4()}"
        compiler_input = live_compiler_input(
            manager.read_compiler_input_v2(),
            manager.project_native_state(request_id=native_state_request_id),
            native_state_request_id=native_state_request_id,
        )
        native_state = compiler_input.snapshot.native_state
        if native_state is None:
            raise RuntimeError("B2/B4 native probe has no native state")
        goal_formula = str(
            native_state.projection["focused_goal"]["formula"]["text"]
        )
        _snapshot, actions = manager.handle_intent(AgentIntent(
            intent="commit_tactic",
            payload={"tactic": REJECTED_TACTIC},
        ))
        failure = next(
            (item for item in actions if item.get("label") == "commit_tactic"),
            None,
        )
        if not isinstance(failure, dict):
            raise RuntimeError("B2/B4 native probe observed no rejected action")
        if tuple(manager.committed_history()) != history_before:
            raise RuntimeError("B2/B4 rejection changed committed history")
        occurrence = manager.execute_native_semantic_batch(
            batch_id=f"n2b3-batch-{uuid.uuid4()}",
            requests=({
                "request_id": f"n2b3-{uuid.uuid4()}",
                "evaluation_prefix": [],
                "query_kind": "proof_term_elaboration",
                "payload": {
                    "operation": "apply",
                    "application_term": APPLICATION_TERM,
                },
            },),
        )
        result = occurrence["result"]["result"]["members"][0]
        descriptor = result.get("descriptor") or {}
        arguments = descriptor.get("arguments") or []
        residuals = descriptor.get("residual_proof_premises") or []
        head = descriptor.get("resolved_head") or {}
        conclusion = descriptor.get("result") or {}
        history_after = tuple(manager.committed_history())
        passed = bool(
            result.get("status") == "accepted"
            and head.get("kind") == "global"
            and str(head.get("identity") or "").endswith(
                ".CCA_CPA_UFCMA"
            )
            and len(arguments) == 6
            and [item.get("actual", {}).get("kind") for item in arguments]
            == ["module", "proof", "proof", "module", "proof", "memory"]
            and [item.get("actual", {}).get("hole") for item in arguments]
            == [False, True, True, False, False, False]
            and len(residuals) == 2
            and conclusion.get("kind") == "formula"
            and descriptor.get("result_convertible_to_current_goal") is True
            and history_after == history_before
        )
        return {
            "schema_version": 1,
            "kind": "proof_state_compiler_b24_native_descriptor_sentinel",
            "rejected_tactic": REJECTED_TACTIC,
            "failure": failure.get("structured_error") or failure.get("error"),
            "attempt_outcome": failure.get("outcome_kind"),
            "attempt_structured_error": (
                failure.get("execution_authority", {}).get("structured_error")
            ),
            "application_term": APPLICATION_TERM,
            "status": result.get("status"),
            "resolved_head": head,
            "input_mode": descriptor.get("input_mode"),
            "input_arguments": descriptor.get("input_arguments") or [],
            "arguments": arguments,
            "explicit_hole_count": descriptor.get("explicit_hole_count"),
            "implicit_argument_count": descriptor.get(
                "implicit_argument_count"
            ),
            "residual_premises": residuals,
            "result_judgment": conclusion,
            "result_convertible_to_current_goal": descriptor.get(
                "result_convertible_to_current_goal"
            ),
            "current_goal_formula": goal_formula,
            "history_unchanged": history_after == history_before,
            "authority": occurrence["authority"],
            "passed": passed,
        }
    finally:
        manager.close()
        if session_path.name.startswith(".ec_session_n2b3_descriptor_"):
            shutil.rmtree(session_path, ignore_errors=True)
            for suffix in (".cli.lock", ".pre_restart.txt"):
                session_path.with_name(
                    session_path.name + suffix
                ).unlink(missing_ok=True)
        if source_output.name.startswith(".n2b3_descriptor_sources_"):
            shutil.rmtree(source_output, ignore_errors=True)


def main() -> int:
    result = run_b24_native_descriptor_sentinel()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
