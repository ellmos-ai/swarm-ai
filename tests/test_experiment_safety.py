"""Regression tests for fail-closed historical experiment boundaries."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from experiments.dungeon.dungeon_template import create_dungeon
from experiments.dungeon.elephant_path_treasure_hunt import (
    restore_dungeon_from_template,
)


def test_dungeon_generator_refuses_non_empty_target(tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    sentinel = target / "README.md"
    sentinel.write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing"):
        create_dungeon(target)
    assert sentinel.read_text(encoding="utf-8") == "do not overwrite"


def test_dungeon_generator_force_requires_its_own_marker(tmp_path):
    target = tmp_path / "unrelated-project"
    target.mkdir()
    sentinel = target / "README.md"
    sentinel.write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(FileExistsError, match="marker"):
        create_dungeon(target, force=True)
    assert sentinel.read_text(encoding="utf-8") == "do not overwrite"


def test_dungeon_restore_uses_repository_template(tmp_path):
    target = tmp_path / "dungeon"
    create_dungeon(target)
    trap = target / "raum_1" / "falle_1.py"
    original = trap.read_bytes()
    trap.write_text("mutated", encoding="utf-8")
    assert restore_dungeon_from_template(target) is True
    assert trap.read_bytes() == original


def _load_maintenance_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments" / "pilot_2026-02" / "maintenance_swarm.py"
    )
    spec = importlib.util.spec_from_file_location("maintenance_swarm_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_dungeon_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments" / "dungeon" / "elephant_path_treasure_hunt.py"
    )
    spec = importlib.util.spec_from_file_location("dungeon_swarm_safety_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_script(relative_path, module_name):
    path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_maintenance_requires_fixture_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("SWARM_ENABLE_LEGACY_EXPERIMENTS", "I_UNDERSTAND")
    monkeypatch.setenv("SWARM_EXPERIMENT_TARGET", str(tmp_path))
    module = _load_maintenance_module()
    with pytest.raises(SystemExit, match="fixture marker"):
        module.require_explicit_opt_in()

    marker = tmp_path / module.FIXTURE_MARKER
    marker.write_text(module.FIXTURE_MARKER_CONTENT, encoding="utf-8")
    monkeypatch.setenv("SWARM_EXPERIMENT_MAX_BUDGET_USD_PER_AGENT", "0.25")
    module.require_explicit_opt_in()


def test_dungeon_requires_fixture_marker_and_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("SWARM_ENABLE_LEGACY_EXPERIMENTS", "I_UNDERSTAND")
    monkeypatch.setenv("SWARM_EXPERIMENT_TARGET", str(tmp_path))
    monkeypatch.setenv("SWARM_EXPERIMENT_MAX_BUDGET_USD_PER_AGENT", "0.25")
    module = _load_dungeon_module()
    with pytest.raises(SystemExit, match="fixture marker"):
        module.require_explicit_opt_in()
    marker = tmp_path / module.DUNGEON_FIXTURE_MARKER
    marker.write_text(module.DUNGEON_FIXTURE_MARKER_CONTENT, encoding="utf-8")
    module.require_explicit_opt_in()


def test_claude_experiment_launchers_are_isolated():
    root = Path(__file__).resolve().parents[1] / "experiments"
    launchers = [
        root / "pilot_2026-02" / "elephant_path_launcher.py",
        root / "pilot_2026-02" / "elephant_path_test_single.py",
        root / "pilot_2026-02" / "maintenance_swarm.py",
        root / "dungeon" / "elephant_path_treasure_hunt.py",
        root / "dungeon" / "elephant_path_treasure_hunt_live.py",
    ]
    for launcher in launchers:
        source = launcher.read_text(encoding="utf-8")
        assert "--safe-mode" in source
        assert "--disallowedTools" in source
        assert "mcp__*" in source
        assert "--max-budget-usd" in source
        assert "--max-total-budget-usd" in source
        assert "SWARM_EXPERIMENT_MAX_BUDGET_USD_PER_AGENT" in source
        assert "C:\\Users\\User" not in source
        assert "MEMORY_FILE" not in source
        assert "MEMORY_BACKUP" not in source


@pytest.mark.parametrize(
    ("relative_path", "entrypoint"),
    [
        ("experiments/pilot_2026-02/elephant_path_launcher.py", "parse_cli"),
        ("experiments/pilot_2026-02/maintenance_swarm.py", "parse_cli"),
        ("experiments/dungeon/elephant_path_treasure_hunt.py", "parse_cli"),
        ("experiments/dungeon/elephant_path_treasure_hunt_live.py", "parse_cli"),
        ("experiments/pilot_2026-02/elephant_path_test_single.py", "main"),
    ],
)
def test_legacy_cli_rejects_unknown_options(
        relative_path, entrypoint, monkeypatch):
    module = _load_script(relative_path, f"strict_cli_{entrypoint}_{len(relative_path)}")
    monkeypatch.setattr("sys.argv", ["experiment", "--testt"])
    with pytest.raises(SystemExit) as exc_info:
        getattr(module, entrypoint)()
    assert exc_info.value.code == 2
