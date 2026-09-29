"""Native loading of proof-stripped source, never certification of admitted proofs."""
from pathlib import Path
import subprocess

import pytest

from core.easycrypt.ec_env import get_ec_env
from core.easycrypt.eval_source_prep import prepare_eval_source
from core.easycrypt.proof_strip import replace_proofs

ROOT = Path(__file__).resolve().parents[1]


def native_load(path: Path) -> None:
    result = subprocess.run(
        ["easycrypt", "-timeout", "10", str(path)], env=get_ec_env(),
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_native_mlkem_clone_survives_actual_eval_source_preparation(tmp_path):
    original = ROOT / "tests/fixtures/proof_strip/mlkem_clone.ec"
    before = original.read_bytes()
    native_load(original)  # The unmodified fixture must itself be valid EasyCrypt.
    prepared = prepare_eval_source(source_file=original, target_lemma="target",
                                   output_dir=tmp_path / "prepared")
    text = prepared.isolated_file.read_text()
    assert "proof indices_not_nil by admit." in text
    assert "rewrite -List.size_eq0" not in text
    assert prepared.manifest["proofs_replaced_total"] == 2
    assert original.read_bytes() == before
    native_load(prepared.isolated_file)
    assert replace_proofs(text) == (text, 0)


@pytest.mark.parametrize("clones", [
    """clone Obligations as C
  proof first by
    (trivial), second by trivial
  proof third by
    (trivial)
  rename [op] "old" as "new"
  remove abbrev helper.
""",
    """clone Obligations as C proof *.
realize first by
  trivial.
realize second
  by trivial.
realize third by trivial.
""",
    """clone Obligations as C proof * by (trivial).
""",
])
def test_native_adjacent_clone_and_realize_boundaries(tmp_path, clones):
    source = """require import AllCore.
abstract theory Obligations.
  op old : int.
  abbrev helper = old.
  axiom first : true.
  axiom second : true.
  axiom third : true.
end Obligations.
""" + clones + "\nop unchanged = (1, 2).\n"
    original = tmp_path / "Original.ec"
    original.write_text(source)
    native_load(original)
    stripped, count = replace_proofs(source)
    assert count > 0
    assert "trivial" not in stripped
    assert stripped.endswith("\nop unchanged = (1, 2).\n")
    prepared = tmp_path / "Prepared.ec"
    prepared.write_text(stripped)
    native_load(prepared)
    assert replace_proofs(stripped) == (stripped, 0)
