"""Atomic, project-local claims for cooperating processes.

Each resource has one O_EXCL-created claim file. Attendance is stored in one
immutable file per participant, so concurrent joins cannot overwrite each other.
"""
from __future__ import annotations

import hashlib
import errno
import json
import math
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TeamLock:
    """Manage atomic resource claims below ``.team-locks``."""

    def __init__(self, project_root, owner: str, *, token: str | None = None):
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("owner must be a non-empty string")
        if token is not None and (not isinstance(token, str) or not token):
            raise ValueError("token must be a non-empty string when provided")
        self.project_root = Path(project_root).resolve()
        self.owner = owner.strip()
        self.token = token or uuid.uuid4().hex
        self.base = self.project_root / ".team-locks"
        self.claim_dir = self.base / "claims"
        self.attendance_dir = self.base / "attendance"
        self.guard_dir = self.base / "guards"

    @staticmethod
    def _write_exclusive(path: Path, payload: dict) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            return False
        try:
            remaining = memoryview(data)
            while remaining:
                written = os.write(fd, remaining)
                if written <= 0:
                    raise OSError("exclusive claim write made no progress")
                remaining = remaining[written:]
            os.fsync(fd)
        except BaseException:
            os.close(fd)
            try:
                path.unlink()
            except OSError:
                pass
            raise
        else:
            os.close(fd)
        return True

    def register(self, role: str, task: str) -> Path:
        """Register attendance without modifying another participant's file."""
        if not isinstance(role, str) or not role.strip():
            raise ValueError("role must be a non-empty string")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")
        payload = {
            "owner": self.owner,
            "token": self.token,
            "role": role,
            "task": task,
            "pid": os.getpid(),
            "joined_at": _utc_now(),
        }
        path = self._attendance_path()
        if not self._write_exclusive(path, payload):
            raise FileExistsError(f"attendance token already exists: {self.token}")
        return path

    @staticmethod
    def _claim_name(kind: str, resource: str) -> str:
        identity = f"{kind}\0{resource}".encode("utf-8")
        return hashlib.sha256(identity).hexdigest() + ".json"

    def _attendance_path(self) -> Path:
        digest = hashlib.sha256(str(self.token).encode("utf-8")).hexdigest()
        return self.attendance_dir / f"{digest}.json"

    @staticmethod
    def _validate_identity(kind: str, resource: str) -> None:
        if (not isinstance(resource, str) or not resource or
                not isinstance(kind, str) or not kind):
            raise ValueError("kind and resource must be non-empty strings")

    @contextmanager
    def _resource_guard(self, kind: str, resource: str, timeout: float = 10.0):
        """Serialize transitions with an OS lock released even after a crash."""
        guard = self.guard_dir / self._claim_name(kind, resource)
        guard.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + timeout
        handle = guard.open("a+b")
        if guard.stat().st_size == 0:
            handle.write(b"\0")
            handle.flush()

        acquired = False
        while not acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError as exc:
                if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    handle.close()
                    raise
                if time.monotonic() >= deadline:
                    handle.close()
                    raise TimeoutError(f"timed out waiting for resource guard: {resource}")
                time.sleep(0.01)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def claim(self, resource: str, *, kind: str = "file", ttl_seconds: int = 86400) -> bool:
        """Atomically claim a resource; exactly one concurrent creator wins."""
        self._validate_identity(kind, resource)
        if not math.isfinite(float(ttl_seconds)) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be finite and greater than zero")
        payload = {
            "kind": kind,
            "resource": resource,
            "owner": self.owner,
            "token": self.token,
            "pid": os.getpid(),
            "claimed_at": _utc_now(),
            "expires_at_epoch": time.time() + ttl_seconds,
        }
        path = self.claim_dir / self._claim_name(kind, resource)
        with self._resource_guard(kind, resource):
            # Expiry is an operator signal, not a lease. Automatic takeover
            # could create two live writers when the original owner is merely
            # slow. Recovery therefore remains an explicit coordinated action.
            return self._write_exclusive(path, payload)

    def release(self, resource: str, *, kind: str = "file") -> bool:
        """Release only a claim owned by this instance token."""
        self._validate_identity(kind, resource)
        path = self.claim_dir / self._claim_name(kind, resource)
        with self._resource_guard(kind, resource):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                return False
            if payload.get("token") != self.token:
                return False
            try:
                path.unlink()
            except FileNotFoundError:
                return False
            return True

    def leave(self) -> bool:
        """Remove this participant's immutable attendance record."""
        path = self._attendance_path()
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

    def attendance(self) -> list[dict]:
        if not self.attendance_dir.exists():
            return []
        records = []
        for path in sorted(self.attendance_dir.glob("*.json")):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return records
