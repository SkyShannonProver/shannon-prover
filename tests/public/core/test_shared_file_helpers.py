"""Contracts of the shared JSON, digest and repository-root helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.digests import sha256_bytes, sha256_file, sha256_json, sha256_text
from core.jsonio import (
    append_jsonl,
    canonical_json,
    read_json_object,
    read_json_object_or_empty,
    read_jsonl,
    strict_json_loads,
)
from core.paths import REPO_ROOT


def test_strict_reader_raises_on_every_bad_file(tmp_path: Path) -> None:
    good = tmp_path / "good.json"
    good.write_text('{"a": 1}', encoding="utf-8")
    assert read_json_object(good) == {"a": 1}

    listing = tmp_path / "list.json"
    listing.write_text("[1]", encoding="utf-8")
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        read_json_object(tmp_path / "missing.json")
    with pytest.raises(ValueError, match="expected JSON object"):
        read_json_object(listing)
    with pytest.raises(json.JSONDecodeError):
        read_json_object(broken)


def test_best_effort_reader_returns_empty_on_every_bad_file(tmp_path: Path) -> None:
    listing = tmp_path / "list.json"
    listing.write_text("[1]", encoding="utf-8")
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    latin = tmp_path / "latin.json"
    latin.write_bytes(b'{"a": "\xff"}')
    for path in (tmp_path / "missing.json", listing, broken, latin, tmp_path):
        assert read_json_object_or_empty(path) == {}


def test_jsonl_round_trip_skips_bad_lines(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "log.jsonl"
    assert read_jsonl(path) == []
    append_jsonl(path, {"b": 2, "a": 1})
    with path.open("a", encoding="utf-8") as stream:
        stream.write("not json\n\n[1]\n")
    append_jsonl(path, {"c": 3})
    assert path.read_text(encoding="utf-8").splitlines()[0] == '{"a": 1, "b": 2}'
    assert read_jsonl(path) == [{"a": 1, "b": 2}, {"c": 3}]
    assert read_jsonl(tmp_path) == []


def test_strict_json_loads_rejects_non_finite_numbers() -> None:
    assert strict_json_loads('{"x": 1.5}') == {"x": 1.5}
    for text in ("NaN", '{"x": Infinity}', "[-Infinity]"):
        with pytest.raises(ValueError, match="non-finite"):
            strict_json_loads(text)


def test_digests_match_hashlib(tmp_path: Path) -> None:
    payload = "δ proof\n" * 200_000
    path = tmp_path / "blob.txt"
    path.write_text(payload, encoding="utf-8")
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert sha256_text(payload) == expected
    assert sha256_bytes(payload.encode("utf-8")) == expected
    assert sha256_file(path) == expected


def test_canonical_json_is_the_spelling_every_identity_was_built_on() -> None:
    """Stored identities (toolchain receipts, resume capsules, cache keys,
    result IDs) were computed from this exact spelling; changing it would
    orphan them."""

    value = {"b": [1, 2.5, None, True], "a": {"z": "δ 证明", "y": ""}, "c": {}}
    text = '{"a":{"y":"","z":"δ 证明"},"b":[1,2.5,null,true],"c":{}}'
    assert canonical_json(value) == text
    assert canonical_json({"a": {"y": "", "z": "δ 证明"}, "c": {}, "b": [1, 2.5, None, True]}) == text
    spelled_out = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert sha256_json(value) == hashlib.sha256(spelled_out).hexdigest()
    assert sha256_json(value) == (
        "ca9ff3a0f0bd573d34fd9f7042d38d67f2d7140383565b3e6eea3fe7ebf45ef0"
    )
    for scalar in ("x", 3, None, [], {}):
        assert sha256_json(scalar) == sha256_text(canonical_json(scalar))


def test_compiler_digest_names_are_the_shared_helpers() -> None:
    from core.easycrypt.proof_state_compiler.contracts import digest

    assert digest.canonical_json is canonical_json
    assert digest.json_sha256 is sha256_json
    assert digest.text_sha256 is sha256_text


def test_repo_root_is_the_checkout_root() -> None:
    assert (REPO_ROOT / "core" / "paths.py").is_file()
    assert (REPO_ROOT / "pyproject.toml").is_file()
