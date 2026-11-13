"""RunConfig.load reads config.json files written before fields were retired."""

import json

from workflow.schemas.config import RunConfig


def test_load_accepts_config_with_retired_iteration_and_mode_keys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "file": "toy.ec",
                "lemma": "L",
                "include_dir": "theories",
                "max_iterations": 2,
                "eval_mode": True,
                "prover": {
                    "mode": "tree",
                    "timeout_minutes": 7,
                    "tree_initial_provers": 1,
                },
            }
        ),
        encoding="utf-8",
    )

    config = RunConfig.load(path)

    assert config.lemma == "L"
    assert config.include_dir == "theories"
    assert config.eval_mode is True
    assert config.prover.timeout_minutes == 7
    assert config.prover.tree_initial_provers == 1
    saved = config.to_dict()
    assert "max_iterations" not in saved
    assert "mode" not in saved["prover"]
