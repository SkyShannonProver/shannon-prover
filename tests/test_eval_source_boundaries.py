"""Declaration layout must not change the selected proof boundary."""
import pytest

from core.easycrypt.eval_source_prep import find_target_proof_block


@pytest.mark.parametrize("head", [
    "lemma target", "local lemma target", "local\nlemma target",
    "local (* locality *)\nlemma target", "local\nlemma\n  target",
])
@pytest.mark.parametrize("body", ["proof.\n  trivial.\nqed.", "admit."])
def test_multiline_declaration_head_preserves_exact_proof(head, body):
    source = f"{head} : true.\n{body}\nlemma later : false.\nproof. admit. qed.\n"
    span = find_target_proof_block(source, "target")
    assert span is not None
    assert source[slice(*span)] == body
    assert span == (source.index(body), source.index(body) + len(body))


@pytest.mark.parametrize("head", ["lemma target", "local\nlemma target"])
def test_missing_proof_cannot_borrow_next_declaration(head):
    source = f"{head} : true.\nlocal\nlemma later : true.\nproof. trivial. qed.\n"
    assert find_target_proof_block(source, "target") is None
