"""Contract checks for the PEP-621 distribution metadata."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_distribution_name_and_pep440_version_are_declared():
    assert 'name = "ellmos-swarm-ai"' in PYPROJECT
    match = re.search(r'^version = "([^"]+)"$', PYPROJECT, re.MULTILINE)
    assert match
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:a\d+|b\d+|rc\d+)?", match.group(1))


def test_stable_cli_entry_points_are_declared():
    expected = {
        "swarm-consensus": "tools.consensus_swarm:main",
        "swarm-benchmark": "tools.benchmark:main",
        "swarm-translate": "tools.translate_swarm:main",
        "swarm-summarize": "tools.summarize_chunks:main",
        "swarm-stigmergy-init": "tools.stigmergy_init:main",
    }
    for command, target in expected.items():
        assert f'{command} = "{target}"' in PYPROJECT


def test_module_manifest_matches_distribution_contract():
    manifest = json.loads(
        (ROOT / "ellmos-module.v2.json").read_text(encoding="utf-8")
    )
    assert manifest["package"] == "ellmos-swarm-ai"
    assert manifest["entrypoints"]["benchmark"] == "python tools/benchmark.py"


def test_release_checklist_exists():
    checklist = (ROOT / "PYPI_RELEASE.md").read_text(encoding="utf-8")
    assert "TestPyPI" in checklist
    assert "PEP-440" in checklist
