"""Cross-process regression tests for atomic team claims."""
from __future__ import annotations

import multiprocessing
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from tools.team_lock import TeamLock


def _claim_worker(root, owner, ready, start, results):
    lock = TeamLock(root, owner)
    lock.register("worker", "concurrent claim test")
    ready.put(owner)
    start.wait(10)
    results.put(lock.claim("shared.txt"))


def _crash_while_guarded(root, ready):
    lock = TeamLock(root, "crashing-worker")
    with lock._resource_guard("file", "crash.txt"):
        ready.put(True)
        ready.close()
        ready.join_thread()
        import os
        os._exit(0)


def test_two_processes_have_one_winner_and_keep_attendance(tmp_path):
    context = multiprocessing.get_context("spawn")
    ready = context.Queue()
    results = context.Queue()
    start = context.Event()
    processes = [
        context.Process(
            target=_claim_worker,
            args=(str(tmp_path), f"agent-{index}", ready, start, results),
        )
        for index in range(2)
    ]
    for process in processes:
        process.start()
    assert {ready.get(timeout=10) for _ in processes} == {"agent-0", "agent-1"}
    start.set()
    winners = [results.get(timeout=10) for _ in processes]
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    assert winners.count(True) == 1
    attendance = TeamLock(tmp_path, "auditor").attendance()
    assert {record["owner"] for record in attendance} == {"agent-0", "agent-1"}


def test_only_owner_token_can_release(tmp_path):
    owner = TeamLock(tmp_path, "owner", token="owner-token")
    other = TeamLock(tmp_path, "other", token="other-token")
    assert owner.claim("db.sqlite", kind="database")
    assert other.release("db.sqlite", kind="database") is False
    assert owner.release("db.sqlite", kind="database") is True


def test_token_cannot_escape_attendance_directory(tmp_path):
    sentinel = tmp_path / "sentinel.json"
    sentinel.write_text("keep", encoding="utf-8")
    lock = TeamLock(tmp_path / "project", "owner", token="../../sentinel")
    attendance = lock.register("worker", "safe token hashing")
    assert attendance.parent == (tmp_path / "project" / ".team-locks" / "attendance")
    assert lock.leave() is True
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_double_release_cannot_delete_new_owner_claim(tmp_path):
    original = TeamLock(tmp_path, "original", token="shared-owner-token")
    newcomer = TeamLock(tmp_path, "newcomer", token="new-token")
    assert original.claim("shared.txt")

    def release_original():
        return original.release("shared.txt")

    def claim_as_newcomer():
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if newcomer.claim("shared.txt"):
                return True
            time.sleep(0.01)
        return False

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(release_original),
            executor.submit(release_original),
            executor.submit(claim_as_newcomer),
        ]
        results = [future.result() for future in futures]

    assert results[:2].count(True) == 1
    assert results[2] is True
    assert newcomer.release("shared.txt") is True


def test_os_guard_is_released_after_hard_process_exit(tmp_path):
    context = multiprocessing.get_context("spawn")
    ready = context.Queue()
    process = context.Process(
        target=_crash_while_guarded,
        args=(str(tmp_path), ready),
    )
    process.start()
    assert ready.get(timeout=10) is True
    process.join(timeout=10)
    assert process.exitcode == 0
    survivor = TeamLock(tmp_path, "survivor")
    assert survivor.claim("crash.txt") is True


def test_expired_claim_is_not_stolen_automatically(tmp_path):
    original = TeamLock(tmp_path, "original")
    newcomer = TeamLock(tmp_path, "newcomer")
    assert original.claim("stale.txt", ttl_seconds=1)
    claim_path = original.claim_dir / original._claim_name("file", "stale.txt")
    import json
    payload = json.loads(claim_path.read_text(encoding="utf-8"))
    payload["expires_at_epoch"] = time.time() - 1
    claim_path.write_text(json.dumps(payload), encoding="utf-8")
    assert newcomer.claim("stale.txt") is False
    assert original.release("stale.txt") is True


def test_nonfinite_ttl_is_rejected(tmp_path):
    lock = TeamLock(tmp_path, "owner")
    for ttl in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finite"):
            lock.claim("invalid.txt", ttl_seconds=ttl)


def test_failed_exclusive_write_does_not_leave_blocking_claim(tmp_path, monkeypatch):
    path = tmp_path / "claim.json"

    def fail_write(*args, **kwargs):
        raise OSError("simulated partial write")

    monkeypatch.setattr(os, "write", fail_write)
    with pytest.raises(OSError, match="partial"):
        TeamLock._write_exclusive(path, {"token": "x"})
    assert not path.exists()
