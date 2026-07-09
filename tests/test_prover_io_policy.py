"""Tests for prover information-source/session-IO policy."""
from __future__ import annotations

from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.prover_io_policy import (  # noqa: E402
    classify_bash_command,
    classify_read_path,
    classify_shell_source_access,
    destructive_tool_denylist,
    has_unquoted_shell_pipe,
    is_session_cli_mutating_command,
)


def test_policy_treats_any_agent_session_cli_as_debug_signal() -> None:
    mutating = classify_bash_command(
        "python3 core/easycrypt/session_cli.py -d s -next -c 'wp.' | head -20"
    )
    probe = classify_bash_command(
        "python3 core/easycrypt/session_cli.py -d s -try -c 'wp.' | grep accepted"
    )
    readonly = classify_bash_command(
        "python3 core/easycrypt/session_cli.py -d s -agent-view"
    )

    assert mutating.decision == "node_fatal"
    assert mutating.source_type == "session_cli_agent_debug_signal"
    assert mutating.mutates_proof_state is True
    assert mutating.lossy is True
    assert mutating.audit_code == "session_cli.agent_call_debug_signal"
    assert probe.decision == "node_fatal"
    assert probe.source_type == "session_cli_agent_debug_signal"
    assert probe.mutates_proof_state is False
    assert probe.lossy is True
    assert readonly.decision == "node_fatal"
    assert readonly.lossy is False


def test_policy_lifecycle_commands_are_same_debug_signal() -> None:
    start = classify_bash_command(
        "python3 core/easycrypt/session_cli.py -d s -start -f x.ec -lemma L"
    )
    restart = classify_bash_command(
        "python3 core/easycrypt/session_cli.py -d s -start --force-restart"
    )

    assert start.decision == "node_fatal"
    assert start.source_type == "session_cli_agent_debug_signal"
    assert start.audit_code == "session_cli.agent_call_debug_signal"
    assert restart.decision == "node_fatal"


def test_policy_allows_source_grep_and_preserves_tactic_pipes() -> None:
    assert classify_bash_command("rg equ_cc eval/examples").decision == "allow"
    assert (
        classify_bash_command("rg equ_cc eval/examples").source_type
        == "shell_source_inspection"
    )
    assert not has_unquoted_shell_pipe(
        "python3 core/easycrypt/session_cli.py -d s -next -c 'case: xs => [|x xs].'"
    )
    assert is_session_cli_mutating_command(
        "python3 core/easycrypt/session_cli.py -d s -chain -c 'wp.'"
    )


def test_shell_source_policy_is_path_based(tmp_path: Path) -> None:
    session = tmp_path / ".ec_session_prover_tree_0_0"

    current = classify_shell_source_access(
        "cat .ec_session_prover_tree_0_0/current.out | head -40",
        cwd=tmp_path,
        current_session_dir=session,
    )
    other = classify_shell_source_access(
        "rg 'while' .ec_session_other/history.ec",
        cwd=tmp_path,
        current_session_dir=session,
    )
    source = classify_shell_source_access(
        "rg CTXT_security eval/examples/MEE-CBC",
        cwd=tmp_path,
        current_session_dir=session,
    )

    assert current is not None
    assert current.decision == "allow"
    assert current.audit_code == "shell_source.inspect"
    assert other is not None
    assert other.decision == "deny"
    assert other.source_type == "shell_other_session_transcript"
    assert source is not None
    assert source.decision == "allow"


def test_policy_classifies_read_paths(tmp_path: Path) -> None:
    session = tmp_path / ".ec_session_prover_tree_0_0"
    current = session / "current.out"
    other_history = tmp_path / ".ec_session_other" / "history.ec"

    # A Claude project/session file NOT under the runner's home: generic
    # internal-trace deny. (Use a foreign absolute path so the assertion does
    # not depend on whose home the test runs under.)
    tool_result = "/srv/elsewhere/.claude/projects/p/session/tool-results/result.txt"
    claude_trace = classify_read_path(tool_result)
    assert claude_trace.decision == "deny"
    assert claude_trace.source_type == "claude_internal_trace"

    # Anything resolving UNDER ~/.claude is escalated to node_fatal by the
    # answer-leak guard (it can expose solved-lemma auto-memory), which fires
    # before the generic internal-trace deny.
    home_trace = str(Path.home() / ".claude" / "projects" / "p" / "session.jsonl")
    leak = classify_read_path(home_trace)
    assert leak.decision == "node_fatal"
    assert leak.source_type == "claude_memory_answer_leak"
    assert classify_read_path(
        str(current),
        cwd=tmp_path,
        current_session_dir=session,
    ).decision == "allow"
    assert classify_read_path(
        str(other_history),
        cwd=tmp_path,
        current_session_dir=session,
    ).decision == "deny"
    assert classify_read_path(
        str(tmp_path / ".ec_session_unknown" / "current.out"),
    ).decision == "warn"
    assert classify_read_path(
        "knowledge/session_trace/processed/by_problem/x/step3.json",
        eval_mode=True,
    ).decision == "deny"
    tmp_artifact = tmp_path / "tmp" / "step3_8min_agent_views" / "tree_0_0"
    worktree_artifact = tmp_path / "worktrees" / "sibling" / "current.out"
    submit_script = (
        tmp_path
        / "workflow"
        / "runs"
        / "r"
        / "iteration_1"
        / "node_memory"
        / "Tree_0_0"
        / "submit_intent.sh"
    )
    assert classify_read_path(str(tmp_artifact), cwd=tmp_path).decision == "deny"
    assert (
        classify_read_path(str(worktree_artifact), cwd=tmp_path).audit_code
        == "read.stale_project_artifact"
    )
    submit_read = classify_read_path(str(submit_script), cwd=tmp_path)
    assert submit_read.decision == "deny"
    assert submit_read.audit_code == "read.manager_bridge_submit_script"
    node_view = (
        tmp_path
        / "workflow"
        / "runs"
        / "r"
        / "iteration_1"
        / "node_memory"
        / "Tree_0_0"
        / "latest_workspace_view.json"
    )
    node_view_read = classify_read_path(str(node_view), cwd=tmp_path)
    assert node_view_read.decision == "allow"
    assert node_view_read.source_type == "current_node_memory"
    assert node_view_read.audit_code == "read.node_memory"
    target_source = tmp_path / "tmp" / "active" / "target.ec"
    target_source.parent.mkdir(parents=True)
    target_source.write_text(
        "lemma target : true.\nproof.\n  admit.\nqed.\n",
        encoding="utf-8",
    )
    allowed = classify_read_path(
        str(target_source),
        cwd=tmp_path,
        allowed_source_files=[target_source],
        target_lemma="target",
    )
    assert allowed.decision == "allow"
    assert allowed.audit_code == "read.active_target_source"
    target_source.write_text(
        "lemma target : true.\nproof.\n  trivial.\nqed.\n",
        encoding="utf-8",
    )
    denied_answer = classify_read_path(
        str(target_source),
        cwd=tmp_path,
        allowed_source_files=[target_source],
        target_lemma="target",
    )
    assert denied_answer.decision == "deny"
    assert denied_answer.audit_code == "read.active_target_source_contains_answer"


def test_eval_mode_denies_original_answer_source_outside_allowed(tmp_path: Path) -> None:
    """Eval mode must deny reading ANY .ec that still holds the target lemma's
    substantive proof — not only the run's isolated, exact-path copy. The
    original corpus file (never in allowed_source_files) is the leak vector."""
    orig = tmp_path / "eval" / "examples" / "orig.ec"
    orig.parent.mkdir(parents=True)
    orig.write_text(
        "lemma target : true.\nproof.\n  by trivial.\nqed.\n", encoding="utf-8",
    )
    # original answer file, NOT in allowed_source_files, eval mode -> denied
    denied = classify_read_path(
        str(orig), cwd=tmp_path, target_lemma="target", eval_mode=True,
    )
    assert denied.decision == "deny"
    assert denied.audit_code == "read.eval_target_answer_source"

    # a scrubbed (admit-only) copy of the same target is safe -> allowed
    scrubbed = tmp_path / "eval" / "examples" / "scrubbed.ec"
    scrubbed.write_text(
        "lemma target : true.\nproof.\n  admit.\nqed.\n", encoding="utf-8",
    )
    assert classify_read_path(
        str(scrubbed), cwd=tmp_path, target_lemma="target", eval_mode=True,
    ).decision == "allow"

    # an unrelated .ec without the target lemma stays allowed (unverified must
    # NOT be gated, or every theory/sibling read would break)
    other = tmp_path / "eval" / "examples" / "other.ec"
    other.write_text(
        "lemma helper : true.\nproof.\n  by trivial.\nqed.\n", encoding="utf-8",
    )
    assert classify_read_path(
        str(other), cwd=tmp_path, target_lemma="target", eval_mode=True,
    ).decision == "allow"

    # outside eval mode the guard does not fire (it is eval-only)
    assert classify_read_path(
        str(orig), cwd=tmp_path, target_lemma="target", eval_mode=False,
    ).decision == "allow"


def test_eval_mode_blocks_historical_eval_reports_and_artifacts(tmp_path: Path) -> None:
    report = tmp_path / "docs" / "reports" / "eval_suite" / "step1_report.md"
    old_metric = (
        tmp_path
        / "artifacts"
        / "eval_suite"
        / "compiler_ladder_matrix"
        / "l4_checked_action_surface"
        / "hard_chacha_step1"
        / "r01"
        / "eval_metrics.json"
    )
    old_source = old_metric.parent / "source" / "ChaChaPoly" / "chacha_poly.ec"
    current_source = (
        tmp_path
        / "artifacts"
        / "eval_suite"
        / "compiler_ladder_matrix"
        / "l1_goal_projection"
        / "hard_chacha_step1"
        / "r01"
        / "source"
        / "ChaChaPoly"
        / "chacha_poly.ec"
    )
    current_node_memory = (
        tmp_path
        / "artifacts"
        / "eval_suite"
        / "compiler_ladder_matrix"
        / "l1_goal_projection"
        / "hard_chacha_step1"
        / "r01"
        / "2026-05-16_1043_step1"
        / "iteration_1"
        / "node_memory"
        / "Tree_0_0"
    )
    current_node_view = current_node_memory / "latest_workspace_view.json"
    old_node_view = (
        tmp_path
        / "artifacts"
        / "eval_suite"
        / "compiler_ladder_matrix"
        / "l4_checked_action_surface"
        / "hard_chacha_step1"
        / "r01"
        / "2026-05-15_0900_step1"
        / "iteration_1"
        / "node_memory"
        / "Tree_0_0"
        / "latest_workspace_view.json"
    )
    current_source.parent.mkdir(parents=True)
    current_source.write_text(
        "lemma step1 : true.\nproof.\n  admit.\nqed.\n",
        encoding="utf-8",
    )
    current_node_view.parent.mkdir(parents=True)
    current_node_view.write_text("{}", encoding="utf-8")

    report_read = classify_read_path(str(report), cwd=tmp_path, eval_mode=True)
    old_metric_read = classify_read_path(str(old_metric), cwd=tmp_path, eval_mode=True)
    old_source_read = classify_read_path(str(old_source), cwd=tmp_path, eval_mode=True)
    current_source_read = classify_read_path(
        str(current_source),
        cwd=tmp_path,
        allowed_source_files=[current_source],
        target_lemma="step1",
        eval_mode=True,
    )
    current_node_read = classify_read_path(
        str(current_node_view),
        cwd=tmp_path,
        allowed_node_memory_dirs=[current_node_memory],
        eval_mode=True,
    )
    old_node_read = classify_read_path(
        str(old_node_view),
        cwd=tmp_path,
        allowed_node_memory_dirs=[current_node_memory],
        eval_mode=True,
    )
    report_rg = classify_shell_source_access(
        "rg step1 docs/reports/eval_suite",
        cwd=tmp_path,
        eval_mode=True,
    )
    current_node_cat = classify_shell_source_access(
        f"cat {current_node_view}",
        cwd=tmp_path,
        allowed_node_memory_dirs=[current_node_memory],
        eval_mode=True,
    )

    assert report_read.decision == "deny"
    assert report_read.audit_code == "read.eval_historical_report"
    assert old_metric_read.decision == "deny"
    assert old_metric_read.audit_code == "read.eval_historical_artifact"
    assert old_source_read.decision == "deny"
    assert old_source_read.audit_code == "read.eval_historical_artifact"
    assert current_source_read.decision == "allow"
    assert current_source_read.audit_code == "read.active_target_source"
    assert current_node_read.decision == "allow"
    assert current_node_read.audit_code == "read.node_memory"
    assert old_node_read.decision == "deny"
    assert old_node_read.audit_code == "read.eval_historical_artifact"
    assert report_rg is not None
    assert report_rg.decision == "deny"
    assert report_rg.audit_code == "read.eval_historical_report"
    assert current_node_cat is not None
    assert current_node_cat.decision == "allow"
    assert current_node_cat.audit_code == "shell_node_memory.inspect"


def test_policy_marks_bridge_and_run_artifact_escapes_node_fatal(tmp_path: Path) -> None:
    run_artifact = (
        tmp_path
        / "workflow"
        / "runs"
        / "2026-05-12_0239_step3"
        / "iteration_1"
        / "manager_bootstrap_0_1.json"
    )
    framework_code = tmp_path / "workflow" / "proof_node_runtime_client.py"
    mcp_server_code = tmp_path / "workflow" / "proof_node_mcp_server.py"
    mcp_config = (
        tmp_path
        / "workflow"
        / "runs"
        / "r"
        / "iteration_1"
        / "runtime_private"
        / "Tree_0_0"
        / "proof_node_mcp_config.json"
    )

    curl = classify_bash_command("curl -s http://127.0.0.1:61222/workspace_view")
    direct_client = classify_bash_command(
        "python3 -m workflow.proof_node_runtime_client --host 127.0.0.1 --port 1 --token x"
    )
    direct_mcp_server = classify_bash_command(
        "python3 -m workflow.proof_node_mcp_server --host 127.0.0.1 --port 1 --token x"
    )
    py_bootstrap = classify_bash_command(
        f"python3 -c \"print(open('{run_artifact}').read())\"",
        cwd=tmp_path,
    )
    submit_script = (
        tmp_path
        / "workflow"
        / "runs"
        / "r"
        / "iteration_1"
        / "node_memory"
        / "Tree_0_0"
        / "submit_intent.sh"
    )
    submit_exec = classify_bash_command(
        f"{submit_script} <<'JSON'\n"
        '{"intent":"inspect_context","payload":{"topic":"goal_info"}}\n'
        "JSON",
        cwd=tmp_path,
    )
    submit_read = classify_bash_command(f"cat {submit_script}", cwd=tmp_path)
    submit_tmp_file = classify_bash_command(
        f"{submit_script} --intent-file {tmp_path / 'tmp' / 'intent.json'}",
        cwd=tmp_path,
    )
    node_intent = submit_script.parent / "next_intent.json"
    submit_pipe = classify_bash_command(
        f"cat {node_intent} | bash {submit_script}",
        cwd=tmp_path,
    )
    legal_node_memory_ls = classify_bash_command(
        "ls -la "
        f"{submit_script.parent / 'workspace_views'} "
        f"{submit_script.parent}",
        cwd=tmp_path,
    )
    legal_node_memory_cat = classify_bash_command(
        f"cat {submit_script.parent / 'latest_workspace_view.json'}",
        cwd=tmp_path,
    )

    assert curl.decision == "node_fatal"
    assert curl.audit_code == "manager_bridge.escape_attempt"
    assert direct_client.decision == "node_fatal"
    assert direct_client.audit_code == "manager_bridge.direct_client"
    assert direct_mcp_server.decision == "node_fatal"
    assert direct_mcp_server.audit_code == "manager_bridge.direct_client"
    assert py_bootstrap.decision == "deny"
    assert py_bootstrap.audit_code == "read.run_artifact_escape"
    assert submit_exec.decision == "allow"
    assert submit_pipe.decision == "allow"
    assert submit_read.decision == "deny"
    assert submit_read.audit_code == "read.manager_bridge_submit_script"
    assert submit_tmp_file.decision == "deny"
    assert submit_tmp_file.audit_code == "read.stale_project_artifact"
    assert legal_node_memory_ls.decision == "allow"
    assert legal_node_memory_ls.source_type == "shell_current_node_memory"
    assert legal_node_memory_ls.audit_code == "shell_node_memory.inspect"
    assert legal_node_memory_cat.decision == "allow"
    assert legal_node_memory_cat.source_type == "shell_current_node_memory"
    assert classify_read_path(str(framework_code)).decision == "deny"
    assert classify_read_path(str(mcp_server_code)).decision == "deny"
    mcp_config_read = classify_read_path(str(mcp_config), cwd=tmp_path)
    assert mcp_config_read.decision == "deny"
    assert mcp_config_read.audit_code == "read.manager_bridge_mcp_config"


def test_hard_denylist_leaves_manager_boundary_to_policy() -> None:
    patterns = destructive_tool_denylist("/tmp/x.ec")

    assert "Bash(*session_cli.py*|*)" not in patterns
    assert "Bash(*session_cli.py*-next* |*)" not in patterns
    assert "Bash(*session_cli.py*-chain* |*)" not in patterns
    assert "Bash(*session_cli.py*-try* |*)" not in patterns
    assert "Read(//private/tmp/*/tasks/*.output)" in patterns
    assert "Agent(*)" in patterns
    assert "Glob(*)" in patterns
    assert "Bash(curl:*)" in patterns
    assert any(pattern.startswith("Read(") and "/.claude/" in pattern for pattern in patterns)
    assert any("workflow/runs" in pattern for pattern in patterns)
    assert any("runtime_private" in pattern for pattern in patterns)
    assert any("proof_node_mcp_config.json" in pattern for pattern in patterns)
    assert any("docs/reports/eval_suite" in pattern for pattern in patterns)
    assert any("artifacts/eval_suite" in pattern for pattern in patterns)
    assert not any(
        pattern.startswith("Bash(") and "workflow/runs/**)" in pattern
        for pattern in patterns
    )
    assert not any("/tmp/**" in pattern for pattern in patterns)
    assert not any("/worktrees/**" in pattern for pattern in patterns)


def test_reading_legal_latest_workspace_view_is_not_a_bridge_escape() -> None:
    # regression: the agent reads `latest_workspace_view.json` (the file the anchor
    # tells it to read) via `python3 -c json.load(open(...))`. The bridge-escape
    # regex used to match the bare substring "workspace_view" in the legal filename
    # and node-fatal-kill the tree. Reading the legal current-node file must NOT be
    # classified as a bridge escape.
    legal = (
        'python3 -c "import json; '
        "json.load(open('/x/artifacts/.../node_memory/Tree_0_0/latest_workspace_view.json'))\""
    )
    d = classify_bash_command(legal)
    assert d.source_type != "manager_bridge_escape_attempt"
    assert d.audit_code != "manager_bridge.escape_attempt"

    # but genuine socket probing of the live bridge view is STILL fatal
    probe = classify_bash_command("lsof -i | grep workspace_view")
    assert probe.source_type == "manager_bridge_escape_attempt"
    # and reading the bridge token directly is STILL fatal
    tok = classify_bash_command("grep 'auth token' /tmp/whatever")
    assert tok.source_type == "manager_bridge_escape_attempt"


def test_claude_project_memory_notes_are_node_fatal_answer_leak() -> None:
    # regression (2026-06-03): when submit_proof_intent flaked, the prover agent
    # rummaged ~/.claude and read project_*.md / MEMORY.md auto-memory notes,
    # which hold SOLVED target-lemma hints -> eval answer leak. The agent reaches
    # them by basename via the memory tool (no "/.claude/" substring to catch), so
    # these must be caught by NAME and treated as node-fatal (a node that saw the
    # answer is discarded), not a kept-alive `deny`.
    home = str(Path.home() / ".claude")
    for path in (
        "project_step4_badi_call_glob_a_trap.md",          # basename via memory tool
        "project_pr_g4_proof_plan.md",
        "MEMORY.md",
        f"{home}/projects/p/memory/MEMORY.md",             # full path
        f"{home}/projects/p/memory/project_x.md",
        f"{home}/projects/p/agent_sessions.jsonl",         # anything under ~/.claude
    ):
        d = classify_read_path(path, eval_mode=True, target_lemma="step4_badi")
        assert d.decision == "node_fatal", (path, d.decision)
        assert d.audit_code == "read.claude_memory_answer_leak", (path, d.audit_code)

    # bash `cat`/`ls` of the memory dir is caught the same way (via the path operand)
    d = classify_bash_command(f"cat {home}/projects/p/memory/project_x.md", eval_mode=True)
    assert d.decision == "node_fatal"
    assert d.audit_code in {"read.claude_memory_answer_leak", "shell_read.claude_memory_answer_leak",
                            "shell_claude_memory_answer_leak"} or "claude_memory" in d.audit_code


def test_memory_note_guard_does_not_overblock_normal_files() -> None:
    # The guard must NOT kill legitimate source/docs reads.
    src = classify_read_path("eval/examples/ChaChaPoly/chacha_poly.ec",
                             eval_mode=True, target_lemma="some_other_lemma")
    assert src.decision != "node_fatal"
    docs = classify_read_path("docs/design/open_source_prep_plan.md", eval_mode=True)
    assert docs.decision == "allow"


def test_denylist_blocks_memory_notes_by_name() -> None:
    # regression (2026-06-05): the by-name blocks were written as bare `*name`
    # globs and the absolute ~/.claude block as a SINGLE-leading-slash path. In a
    # Read()/Edit() permission rule a single leading slash anchors to the PROJECT
    # ROOT (gitignore semantics), and a bare `*name` glob does NOT match outside
    # the cwd subtree — so BOTH silently failed to match the real absolute memory
    # path and a prover Read its target's solved-lemma note in FULL before being
    # node-killed only reactively. The working forms (verified empirically +
    # Claude Code permission docs) are `**/name` for basenames and `//abs` (double
    # slash = filesystem root) / `~` for absolute home paths.
    patterns = destructive_tool_denylist("eval/examples/ChaChaPoly/chacha_poly.ec",
                                         project_root=".")
    assert "Read(**/MEMORY.md)" in patterns
    assert "Read(**/project_*.md)" in patterns
    assert "Read(**/memory/**)" in patterns
    # absolute ~/.claude blocks must use a DOUBLE leading slash (or `~`), never a
    # single slash (which would anchor to the project root and never fire).
    home = str(Path.home())
    assert f"Read(/{home}/.claude/**)" in patterns
    assert "Read(~/.claude/**)" in patterns
    assert not any(p == f"Read({home}/.claude/**)" for p in patterns), (
        "single-leading-slash absolute pattern anchors to project root and leaks"
    )


def test_denylist_blocks_memory_writes_not_just_reads() -> None:
    # regression (2026-06-03): a stuck prover used Edit/Write to record a blocker
    # note INTO ~/.claude project memory (creating project_*.md + editing
    # MEMORY.md). Writes must be pre-blocked too, symmetric with the read blocks.
    # (2026-06-05) same `**/` / `//` anchoring fix as the read blocks above.
    patterns = destructive_tool_denylist("eval/examples/ChaChaPoly/chacha_poly.ec",
                                         project_root=".")
    for tool in ("Edit", "Write", "MultiEdit"):
        assert f"{tool}(**/MEMORY.md)" in patterns, tool
        assert f"{tool}(**/project_*.md)" in patterns, tool
        assert f"{tool}(**/memory/**)" in patterns, tool
    # the path-based guard (reused for Edit/Write targets by the runtime watchdog)
    # node-fatals a write whose target is a memory note
    d = classify_read_path("project_step4_badi_seq_drops_eqp.md",
                           eval_mode=True, target_lemma="step4_badi")
    assert d.decision == "node_fatal"
    assert d.audit_code == "read.claude_memory_answer_leak"


# ---- (A) current-run isolated source copy (merged from
# ---- test_prover_io_policy_run_source.py) -----------------------------------
#
# Found 2026-05-30 in a live step4_badi run: the prover needed a called game
# procedure's body (`CPA_game.main`, defined in the imported `ske.ec`). The
# structured view did not surface it, so the agent read the source — a sibling
# `.ec` under the run's own isolated copy `<run>/source/ChaChaPoly/ske.ec`. But
# because that copy lives under `artifacts/eval_suite/`, the policy denied it as
# a "forbidden eval historical artifact" and (after 3 strikes) the
# session-hygiene watchdog killed the whole tree — discarding its committed
# proof work over a LEGAL source read.
#
# (A) recognizes `<run>/source/...` as the run's own source: the target file
# plus the sibling/dependency `.ec`/`.eca` it imports. Reading them is allowed;
# only a sibling that itself holds the target lemma's substantive proof, or a
# genuine prior-run artifact, stays denied.


def _layout(tmp: Path, *, target_proof: str = "admit.", sibling_body: str = "") -> dict:
    root = tmp / "artifacts/eval_suite/run/l4/x/r01/source/ChaChaPoly"
    root.mkdir(parents=True)
    (root / "chacha.ec").write_text(
        "require import AllCore.\nlocal lemma tgt : true.\nproof.\n" + target_proof + "\nqed.\n")
    (root / "ske.ec").write_text(
        "module CPA_game = { proc main () = { } }.\n" + sibling_body)
    return {"cwd": str(tmp), "src": root, "allowed": [str(root / "chacha.ec")]}


def test_sibling_dependency_read_is_allowed(tmp_path: Path) -> None:
    L = _layout(tmp_path)
    d = classify_read_path(str(L["src"] / "ske.ec"), cwd=L["cwd"],
                           allowed_source_files=L["allowed"], target_lemma="tgt",
                           eval_mode=True)
    assert d.decision == "allow", d
    assert d.source_type == "current_run_isolated_source"


def test_find_within_run_source_is_allowed(tmp_path: Path) -> None:
    L = _layout(tmp_path)
    run_source = str(L["src"].parent)  # <run>/source
    d = classify_bash_command(f'find {run_source} -name "*.ec"', cwd=L["cwd"],
                              allowed_source_files=L["allowed"], target_lemma="tgt",
                              eval_mode=True)
    assert d.decision == "allow", d


def test_target_file_admit_scrubbed_is_allowed(tmp_path: Path) -> None:
    L = _layout(tmp_path, target_proof="admit.")
    d = classify_read_path(str(L["src"] / "chacha.ec"), cwd=L["cwd"],
                           allowed_source_files=L["allowed"], target_lemma="tgt",
                           eval_mode=True)
    assert d.decision == "allow", d


def test_prior_run_artifact_still_denied(tmp_path: Path) -> None:
    L = _layout(tmp_path)
    # a DIFFERENT run's internal artifact, NOT under this run's /source/
    prior = tmp_path / "artifacts/eval_suite/run/l4/x/r99/iteration_1/node_memory/x/history.ec"
    prior.parent.mkdir(parents=True)
    prior.write_text("proc.\n")
    d = classify_read_path(str(prior), cwd=L["cwd"], allowed_source_files=L["allowed"],
                           target_lemma="tgt", eval_mode=True)
    assert d.decision == "deny", d
    assert d.source_type == "eval_historical_artifact"


def test_sibling_holding_target_proof_still_denied(tmp_path: Path) -> None:
    # answer-leak guard: a file in the run's own tree that contains the target
    # lemma's SUBSTANTIVE proof must stay denied even though it's "own source".
    L = _layout(tmp_path, sibling_body=(
        "local lemma tgt : true.\nproof.\nby rewrite /= /#; smt().\nqed.\n"))
    d = classify_read_path(str(L["src"] / "ske.ec"), cwd=L["cwd"],
                           allowed_source_files=L["allowed"], target_lemma="tgt",
                           eval_mode=True)
    assert d.decision == "deny", d
    assert d.source_type == "active_target_source_contains_answer"
