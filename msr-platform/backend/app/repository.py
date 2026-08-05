"""Persistencia de jobs en SQLite (`sqlite3` estándar, transacciones explícitas).

Garantías:
- Los jobs (y su histórico de eventos) sobreviven a un reinicio del backend.
- Idempotencia: la misma `Idempotency-Key` devuelve siempre el mismo job.
- Lock por objetivo: como máximo un job mutativo activo por `logical_target_id`
  (índice único parcial), de modo que dos peticiones simultáneas no pueden
  lanzar dos operaciones sobre la misma instancia.
- No se persisten secretos: sólo payloads construidos por el backend.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from .jobs import ACTIVE_STATES, JobEvent, JobState, JobType, PatchJob
from .providers.base import Target

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id                  TEXT PRIMARY KEY,
    job_type            TEXT NOT NULL,
    task_id             TEXT NOT NULL,
    ring_number         INTEGER NOT NULL,
    provider            TEXT NOT NULL,
    provider_reference  TEXT,
    state               TEXT NOT NULL,
    dry_run             INTEGER NOT NULL DEFAULT 1,
    correlation_id      TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    started_at          TEXT,
    completed_at        TEXT,
    error_code          TEXT,
    error_message       TEXT,
    idempotency_key     TEXT NOT NULL,
    request_payload     TEXT NOT NULL DEFAULT '{}',
    result_payload      TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_jobs_task ON jobs(task_id);
CREATE INDEX IF NOT EXISTS ix_jobs_state ON jobs(state);

CREATE TABLE IF NOT EXISTS job_targets (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id             TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    logical_target_id  TEXT NOT NULL,
    instance_id        TEXT,
    payload            TEXT NOT NULL DEFAULT '{}',
    active             INTEGER NOT NULL DEFAULT 1
);
-- Lock por objetivo: sólo un job mutativo activo por objetivo lógico.
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_logical_target
    ON job_targets(logical_target_id) WHERE active = 1;
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_instance
    ON job_targets(instance_id) WHERE active = 1 AND instance_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_job_targets_job ON job_targets(job_id);

CREATE TABLE IF NOT EXISTS job_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    state       TEXT NOT NULL,
    message     TEXT NOT NULL,
    actor       TEXT NOT NULL DEFAULT 'msr-platform',
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_job_events_job ON job_events(job_id);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key         TEXT PRIMARY KEY,
    job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    scope       TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""


class TargetBusyError(RuntimeError):
    """Ya existe un job mutativo activo sobre el mismo objetivo."""

    def __init__(self, logical_target_id: str, job_id: str | None = None):
        super().__init__(f"El objetivo {logical_target_id} ya tiene un job activo.")
        self.logical_target_id = logical_target_id
        self.job_id = job_id


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class JobRepository:
    """Repositorio de jobs. Una instancia por proceso; conexión reutilizada."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        if db_path != ":memory:":
            directory = os.path.dirname(os.path.abspath(db_path))
            os.makedirs(directory, exist_ok=True)
        self._conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        if db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    def _row_to_job(self, row: sqlite3.Row, with_events: bool = False) -> PatchJob:
        targets = tuple(
            Target.from_dict(json.loads(r["payload"]))
            for r in self._conn.execute(
                "SELECT payload FROM job_targets WHERE job_id = ? ORDER BY id", (row["id"],)))
        job = PatchJob(
            id=row["id"],
            job_type=JobType(row["job_type"]),
            task_id=row["task_id"],
            ring_number=row["ring_number"],
            provider=row["provider"],
            state=JobState(row["state"]),
            dry_run=bool(row["dry_run"]),
            provider_reference=row["provider_reference"],
            correlation_id=row["correlation_id"],
            idempotency_key=row["idempotency_key"],
            created_at=_parse(row["created_at"]),
            updated_at=_parse(row["updated_at"]),
            started_at=_parse(row["started_at"]),
            completed_at=_parse(row["completed_at"]),
            error_code=row["error_code"],
            error_message=row["error_message"],
            request_payload=json.loads(row["request_payload"]),
            result_payload=json.loads(row["result_payload"]),
            targets=targets,
        )
        if with_events:
            job.events = tuple(self.list_events(job.id))
        return job

    # ------------------------------------------------------------------
    def create_job(self, job: PatchJob, *, scope: str = "approve") -> tuple[PatchJob, bool]:
        """Crea el job tomando el lock de sus objetivos, de forma transaccional.

        Devuelve `(job, created)`. Si la `idempotency_key` ya existe, devuelve el
        job original con `created=False`. Si otro job activo ocupa el objetivo,
        lanza `TargetBusyError`.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute(
                "SELECT job_id FROM idempotency_keys WHERE key = ?", (job.idempotency_key,)).fetchone()
            if existing:
                conn.execute("COMMIT")
                return self.get_job(existing["job_id"], with_events=True), False

            for target in job.targets:
                busy = conn.execute(
                    "SELECT job_id FROM job_targets WHERE logical_target_id = ? AND active = 1",
                    (target.logical_target_id,)).fetchone()
                if busy:
                    conn.execute("ROLLBACK")
                    raise TargetBusyError(target.logical_target_id, busy["job_id"])

            conn.execute(
                """INSERT INTO jobs (id, job_type, task_id, ring_number, provider, provider_reference,
                                     state, dry_run, correlation_id, created_at, updated_at, started_at,
                                     completed_at, error_code, error_message, idempotency_key,
                                     request_payload, result_payload)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job.id, job.job_type.value, job.task_id, job.ring_number, job.provider,
                 job.provider_reference, job.state.value, int(job.dry_run), job.correlation_id,
                 _iso(job.created_at), _iso(job.updated_at), _iso(job.started_at),
                 _iso(job.completed_at), job.error_code, job.error_message, job.idempotency_key,
                 json.dumps(job.request_payload, ensure_ascii=False),
                 json.dumps(job.result_payload, ensure_ascii=False)))
            active = 0 if job.terminal else 1
            for target in job.targets:
                conn.execute(
                    """INSERT INTO job_targets (job_id, logical_target_id, instance_id, payload, active)
                       VALUES (?,?,?,?,?)""",
                    (job.id, target.logical_target_id, target.instance_id,
                     json.dumps(target.as_dict(), ensure_ascii=False), active))
            conn.execute(
                "INSERT INTO idempotency_keys (key, job_id, scope, created_at) VALUES (?,?,?,?)",
                (job.idempotency_key, job.id, scope, _iso(job.created_at)))
            conn.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            conn.execute("ROLLBACK")
            if "ux_active" in str(exc):
                target_id = job.targets[0].logical_target_id if job.targets else "?"
                raise TargetBusyError(target_id) from exc
            raise
        except TargetBusyError:
            raise
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return job, True

    # ------------------------------------------------------------------
    def save_job(self, job: PatchJob) -> PatchJob:
        """Persiste el estado del job y libera el lock si es terminal."""
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """UPDATE jobs SET provider_reference = ?, state = ?, dry_run = ?, updated_at = ?,
                                   started_at = ?, completed_at = ?, error_code = ?, error_message = ?,
                                   request_payload = ?, result_payload = ?
                   WHERE id = ?""",
                (job.provider_reference, job.state.value, int(job.dry_run), _iso(job.updated_at),
                 _iso(job.started_at), _iso(job.completed_at), job.error_code, job.error_message,
                 json.dumps(job.request_payload, ensure_ascii=False),
                 json.dumps(job.result_payload, ensure_ascii=False), job.id))
            if job.terminal:
                conn.execute("UPDATE job_targets SET active = 0 WHERE job_id = ?", (job.id,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return job

    def append_event(self, job_id: str, state: JobState, message: str,
                     actor: str = "msr-platform") -> JobEvent:
        event = JobEvent(job_id=job_id, state=state.value, message=message[:2000], actor=actor)
        self._conn.execute(
            "INSERT INTO job_events (job_id, state, message, actor, created_at) VALUES (?,?,?,?,?)",
            (job_id, event.state, event.message, event.actor, _iso(event.created_at)))
        return event

    def has_event(self, job_id: str, message: str) -> bool:
        """Evita duplicar eventos/logs cuando el polling repite la reconciliación."""
        row = self._conn.execute(
            "SELECT 1 FROM job_events WHERE job_id = ? AND message = ? LIMIT 1",
            (job_id, message[:2000])).fetchone()
        return row is not None

    def list_events(self, job_id: str) -> list[JobEvent]:
        return [
            JobEvent(job_id=r["job_id"], state=r["state"], message=r["message"], actor=r["actor"],
                     created_at=_parse(r["created_at"]), id=r["id"])
            for r in self._conn.execute(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY id", (job_id,))]

    # ------------------------------------------------------------------
    def get_job(self, job_id: str, with_events: bool = False) -> PatchJob | None:
        row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row, with_events) if row else None

    def get_job_by_idempotency_key(self, key: str) -> PatchJob | None:
        row = self._conn.execute(
            "SELECT job_id FROM idempotency_keys WHERE key = ?", (key,)).fetchone()
        return self.get_job(row["job_id"], with_events=True) if row else None

    def list_jobs_for_task(self, task_id: str, limit: int = 50) -> list[PatchJob]:
        rows = self._conn.execute(
            "SELECT * FROM jobs WHERE task_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
            (task_id, limit)).fetchall()
        return [self._row_to_job(r) for r in rows]

    def _active_placeholders(self) -> tuple[str, tuple[str, ...]]:
        states = tuple(s.value for s in sorted(ACTIVE_STATES, key=lambda s: s.value))
        return ",".join("?" for _ in states), states

    def active_job_for_task(self, task_id: str) -> PatchJob | None:
        placeholders, states = self._active_placeholders()
        row = self._conn.execute(
            f"SELECT * FROM jobs WHERE task_id = ? AND state IN ({placeholders}) "
            "ORDER BY created_at DESC, id DESC LIMIT 1", (task_id, *states)).fetchone()
        return self._row_to_job(row, with_events=True) if row else None

    def active_job_for_target(self, logical_target_id: str) -> PatchJob | None:
        row = self._conn.execute(
            "SELECT job_id FROM job_targets WHERE logical_target_id = ? AND active = 1 LIMIT 1",
            (logical_target_id,)).fetchone()
        return self.get_job(row["job_id"], with_events=True) if row else None

    def list_active_jobs(self) -> list[PatchJob]:
        placeholders, states = self._active_placeholders()
        rows = self._conn.execute(
            f"SELECT * FROM jobs WHERE state IN ({placeholders}) ORDER BY created_at", states).fetchall()
        return [self._row_to_job(r) for r in rows]

    def clear(self) -> None:
        """Sólo para `POST /api/reset` y para los tests: vacía el histórico."""
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            for table in ("idempotency_keys", "job_events", "job_targets", "jobs"):
                conn.execute(f"DELETE FROM {table}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
