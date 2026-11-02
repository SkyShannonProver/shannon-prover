from __future__ import annotations

from workflow.easycrypt_source_inventory import (
    detect_admit_dependencies,
    extract_declarations,
)
from workflow.project_driver import scan_admit_lemmas


def test_extract_declarations_keeps_qualified_names_in_statement() -> None:
    source = """
(* lemma fake : true. proof. admit. qed. *)
lemma helper : A.main = B.main.
proof. trivial. qed.

local equiv bridge : A.main ~ B.main : true ==> true.
proof. admit. qed.

axiom bound : Pr[A.main() @ &m : res] <= 1%r.
"""

    declarations = extract_declarations(source)

    assert [item["name"] for item in declarations] == ["helper", "bridge", "bound"]
    assert declarations[0]["statement"] == "lemma helper : A.main = B.main."
    assert declarations[0]["status"] == "proved"
    assert declarations[1]["status"] == "admit"
    assert declarations[2]["status"] == "axiom"


def test_detect_admit_dependencies_is_project_driver_metadata_only() -> None:
    source = """
lemma helper : true.
proof. admit. qed.

lemma target : true.
proof. apply helper. qed.
"""
    declarations = extract_declarations(source)

    dependencies = detect_admit_dependencies(source, declarations)

    assert dependencies["helper"]["deps"] == []
    assert dependencies["helper"]["can_prove"]


def test_project_driver_consumes_static_inventory(tmp_path) -> None:
    source = tmp_path / "Project.ec"
    source.write_text(
        "lemma helper : true.\nproof. trivial. qed.\n\n"
        "lemma target : true.\nproof. admit. qed.\n",
        encoding="utf-8",
    )

    inventory = scan_admit_lemmas(source)

    assert [(item["name"], item["status"]) for item in inventory] == [
        ("helper", "proved"),
        ("target", "admit"),
    ]
