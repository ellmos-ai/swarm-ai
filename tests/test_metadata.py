"""Metadata and manifest parity tests for ellmos-ai/swarm-ai."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_and_pyproject_version_parity():
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version_match = re.search(r'^version = "([^"]+)"', pyproject_text, re.MULTILINE)
    assert version_match, "version not found in pyproject.toml"
    pyproject_version = version_match.group(1)

    manifest_path = ROOT / "ellmos-module.v2.json"
    assert manifest_path.exists(), "ellmos-module.v2.json must exist"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["package"] == "ellmos-swarm-ai"
    assert manifest["id"] == "swarm_ai"
    assert pyproject_version == "0.1.0"


def test_cli_entrypoints_parity():
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    expected_tools = [
        ("tools/consensus_swarm.py", "swarm-consensus"),
        ("tools/benchmark.py", "swarm-benchmark"),
        ("tools/translate_swarm.py", "swarm-translate"),
        ("tools/summarize_chunks.py", "swarm-summarize"),
        ("tools/stigmergy_init.py", "swarm-stigmergy-init"),
    ]

    for rel_path, entrypoint in expected_tools:
        tool_file = ROOT / rel_path
        assert tool_file.exists(), f"Expected tool file {rel_path} must exist"
        assert entrypoint in pyproject_text, f"Entrypoint {entrypoint} must be in pyproject.toml"


def test_llms_txt_and_documentation_parity():
    llms_txt = (ROOT / "llms.txt").read_text(encoding="utf-8")
    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "https://github.com/ellmos-ai/swarm-ai" in llms_txt
    assert "https://github.com/ellmos-ai/swarm-ai" in readme_en
    assert "https://github.com/ellmos-ai/swarm-ai" in readme_de

    # Verify key patterns documented
    patterns = [
        "tools/consensus_swarm.py",
        "tools/stigmergy_api.py",
        "tools/translate_swarm.py",
        "tools/summarize_chunks.py",
        "tools/runner.py",
    ]
    for pattern in patterns:
        assert pattern in llms_txt, f"Pattern {pattern} must be mentioned in llms.txt"
        assert (ROOT / pattern).exists(), f"File {pattern} must exist"


def test_utf8_integrity_across_markdown():
    md_files = list(ROOT.glob("*.md")) + list((ROOT / "konzepte").glob("*.md"))
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        assert "\ufffd" not in content, f"Replacement character detected in {md_file}"


def test_pep621_classifiers_and_urls_parity():
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "Programming Language :: Python :: 3" in pyproject_text
    assert "Programming Language :: Python :: 3.10" in pyproject_text
    assert "Programming Language :: Python :: 3.13" in pyproject_text
    assert "License :: OSI Approved :: MIT License" in pyproject_text
    assert "Operating System :: OS Independent" in pyproject_text
    assert "Documentation = " in pyproject_text
    assert '"Bug Tracker" = ' in pyproject_text
    assert "Changelog = " in pyproject_text
    assert "Security = " in pyproject_text


def test_security_policy_bilingual_parity():
    security_md = ROOT / "SECURITY.md"
    assert security_md.exists(), "SECURITY.md must exist"
    content = security_md.read_text(encoding="utf-8")
    assert "# Security Policy / Sicherheitsrichtlinie" in content
    assert "## English" in content
    assert "## Deutsch" in content
    assert "security@ellmos.ai" in content
    assert "support@lukasgeiger.com" in content
    assert "lukas@open-bricks.org" in content


def test_ci_workflow_parity():
    ci_path = ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_path.exists(), "ci.yml must exist"
    ci_text = ci_path.read_text(encoding="utf-8")
    assert "ubuntu-latest" in ci_text
    assert "windows-latest" in ci_text
    assert "macos-latest" in ci_text
    assert "3.10" in ci_text
    assert "3.13" in ci_text

