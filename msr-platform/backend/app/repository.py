"""Persistencia de jobs en SQLite (`sqlite3` estándar, transacciones explícitas).

Garantías:
- Los jobs (y su histórico de eventos) sobreviven a un reinicio del backend.
- Idempotencia: la misma `Idempotency-Key` devuelve siempre el mismo job.
- Lock por objetivo: como máximo un job mutativo activo por `logical_target_id`
  (índice único parcial), de modo que dos peticiones simultáneas no pueden
  lanzar dos operaciones sobre la misma instancia.
- No se persisten secretos: sólo payloads construidos por el backend.

Concurrencia: una conexión SQLite no se comparte entre threads. Cada operación
abre su propia conexión (`connection()`) con `WAL` y `busy_timeout`, y las
escrituras se agrupan en `BEGIN IMMEDIATE` (`transaction()`). La única excepción
es `:memory:`, donde cada conexión nueva sería *otra* base de datos: en ese caso
se reutiliza una conexión compartida serializada con un `threading.RLock`.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from .jobs import ACTIVE_STATES, JobEvent, JobState, JobType, PatchJob
from .lab import LAB_STATE_UNKNOWN, RECONCILE_IDLE, LabTarget
from .providers.base import Target

MEMORY_PATH = ":memory:"
BUSY_TIMEOUT_MS = 5000
CONNECT_TIMEOUT_SECONDS = 5

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

-- Laboratorio reutilizable: describe la instancia vulnerable de la PoC para
-- poder distinguir `rollback` de `reset_lab`. No dispara ninguna operación.
CREATE TABLE IF NOT EXISTS lab_targets (
    logical_lab_id              TEXT PRIMARY KEY,
    current_instance_id         TEXT,
    account_id                  TEXT,
    region                      TEXT,
    vulnerable_ami_id           TEXT,
    launch_template_id          TEXT,
    launch_template_version     TEXT,
    autoscaling_group_name      TEXT,
    expected_vulnerable_package TEXT,
    expected_vulnerable_version TEXT,
    candidate_releasever        TEXT,
    expected_fixed_kernel       TEXT,
    required_tags               TEXT NOT NULL DEFAULT '{}',
    last_reset_job_id           TEXT,
    previous_instance_id        TEXT,
    lab_state                   TEXT NOT NULL DEFAULT 'unknown',
    current_kernel              TEXT,
    advisory_applicable         INTEGER,
    ssm_state                   TEXT,
    health_state                TEXT,
    evidence_source             TEXT,
    last_patch_job_id           TEXT,
    last_patch_execution_id     TEXT,
    last_patch_at               TEXT,
    last_reset_execution_id     TEXT,
    reconciliation_state        TEXT NOT NULL DEFAULT 'idle',
    last_reconciled_at          TEXT,
    last_reconciliation_error   TEXT,
    last_correlation_id         TEXT,
    updated_at                  TEXT NOT NULL
);

-- Lock local de operación del laboratorio (patch, reset o reconciliación) para
-- los modos `mock` y `aws-dry-run`. En `aws-real` el lock equivalente vive en
-- DynamoDB, porque las tasks de Fargate no comparten este fichero. El lock
-- caduca (`expires_at`) para que la caída de un proceso no lo bloquee para
-- siempre, y `owner` es el `correlation_id` de la operación: sólo su dueño lo
-- libera.
CREATE TABLE IF NOT EXISTS lab_locks (
    logical_lab_id  TEXT PRIMARY KEY,
    holder          TEXT NOT NULL,
    correlation_id  TEXT NOT NULL,
    reason          TEXT NOT NULL DEFAULT '',
    operation       TEXT NOT NULL DEFAULT '',
    acquired_at     TEXT NOT NULL,
    expires_at      TEXT NOT NULL
);

-- Verificaciones humanas de las puertas HITL: son decisiones que bloquean el
-- recorrido, así que deben sobrevivir a un reinicio igual que los jobs.
CREATE TABLE IF NOT EXISTS hitl_verifications (
    task_id          TEXT NOT NULL,
    verification_key TEXT NOT NULL,
    payload          TEXT NOT NULL DEFAULT '{}',
    created_at       TEXT NOT NULL,
    PRIMARY KEY (task_id, verification_key)
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
    """Repositorio de jobs con una conexión SQLite por operación."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.in_memory = db_path == MEMORY_PATH
        # Serializa el acceso a la conexión compartida de `:memory:`. Es
        # reentrante para permitir lecturas anidadas dentro de una operación.
        self._guard = threading.RLock()
        self._shared: sqlite3.Connection | None = None
        self._closed = False
        if not self.in_memory:
            directory = os.path.dirname(os.path.abspath(db_path))
            os.makedirs(directory, exist_ok=True)
        else:
            self._shared = self._connect()
        with self.connection() as conn:
            conn.executescript(SCHEMA)
            self._apply_migrations(conn)

    @staticmethod
    def _apply_migrations(conn: sqlite3.Connection) -> None:
        """Columnas añadidas después de la creación original del esquema."""
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(lab_targets)")}
        for column in ("autoscaling_group_name", "candidate_releasever",
                       "expected_fixed_kernel", "previous_instance_id", "current_kernel",
                       "ssm_state", "health_state", "evidence_source", "last_patch_job_id",
                       "last_patch_execution_id", "last_patch_at",
                       "last_reset_execution_id",
                       "last_reconciled_at", "last_reconciliation_error",
                       "last_correlation_id"):
            if column not in columns:
                conn.execute(f"ALTER TABLE lab_targets ADD COLUMN {column} TEXT")
        if "advisory_applicable" not in columns:
            conn.execute("ALTER TABLE lab_targets ADD COLUMN advisory_applicable INTEGER")
        if "lab_state" not in columns:
            conn.execute("ALTER TABLE lab_targets ADD COLUMN lab_state TEXT "
                         "NOT NULL DEFAULT 'unknown'")
        if "reconciliation_state" not in columns:
            conn.execute("ALTER TABLE lab_targets ADD COLUMN reconciliation_state TEXT "
                         "NOT NULL DEFAULT 'idle'")
        lock_columns = {row["name"] for row in conn.execute("PRAGMA table_info(lab_locks)")}
        if "operation" not in lock_columns:
            conn.execute("ALTER TABLE lab_locks ADD COLUMN operation TEXT NOT NULL DEFAULT ''")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            isolation_level=None,
            timeout=CONNECT_TIMEOUT_SECONDS,
            # Sólo la conexión compartida de `:memory:` cruza threads, y está
            # protegida por `self._guard`.
            check_same_thread=not self.in_memory,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if not self.in_memory:
            conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Conexión de uso exclusivo para la operación en curso."""
        if self.in_memory and self._closed:
            raise RuntimeError("El repositorio en memoria ya está cerrado.")
        if self._shared is not None:
            with self._guard:
                yield self._shared
            return
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Escritura atómica: `BEGIN IMMEDIATE` + `COMMIT`/`ROLLBACK`."""
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    def close(self) -> None:
        """Cierra la conexión compartida de `:memory:`.

        Con una base en fichero no hay nada que cerrar: cada operación usa su
        propia conexión, así que cerrar el repositorio no invalida las que se
        abran después.
        """
        with self._guard:
            self._closed = True
            if self._shared is not None:
                self._shared.close()
                self._shared = None

    # ------------------------------------------------------------------
    @staticmethod
    def _events(conn: sqlite3.Connection, job_id: str) -> tuple[JobEvent, ...]:
        return tuple(
            JobEvent(job_id=r["job_id"], state=r["state"], message=r["message"], actor=r["actor"],
                     created_at=_parse(r["created_at"]), id=r["id"])
            for r in conn.execute(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY id", (job_id,)))

    def _row_to_job(self, conn: sqlite3.Connection, row: sqlite3.Row,
                    with_events: bool = False) -> PatchJob:
        targets = tuple(
            Target.from_dict(json.loads(r["payload"]))
            for r in conn.execute(
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
            job.events = self._events(conn, job.id)
        return job

    def _job_by_id(self, conn: sqlite3.Connection, job_id: str,
                   with_events: bool = False) -> PatchJob | None:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(conn, row, with_events) if row else None

    # ------------------------------------------------------------------
    def create_job(self, job: PatchJob, *, scope: str = "approve") -> tuple[PatchJob, bool]:
        """Crea el job tomando el lock de sus objetivos, de forma transaccional.

        Devuelve `(job, created)`. Si la `idempotency_key` ya existe, devuelve el
        job original con `created=False`. Si otro job activo ocupa el objetivo,
        lanza `TargetBusyError`.
        """
        replayed_id: str | None = None
        try:
            with self.transaction() as conn:
                existing = conn.execute(
                    "SELECT job_id FROM idempotency_keys WHERE key = ?",
                    (job.idempotency_key,)).fetchone()
                if existing:
                    replayed_id = existing["job_id"]
                else:
                    self._insert_job(conn, job, scope)
        except sqlite3.IntegrityError as exc:
            if "ux_active" in str(exc):
                target_id = job.targets[0].logical_target_id if job.targets else "?"
                raise TargetBusyError(target_id) from exc
            raise
        if replayed_id is not None:
            replayed = self.get_job(replayed_id, with_events=True)
            if replayed is not None:
                return replayed, False
        return job, True

    def _insert_job(self, conn: sqlite3.Connection, job: PatchJob, scope: str) -> None:
        for target in job.targets:
            busy = conn.execute(
                "SELECT job_id FROM job_targets WHERE logical_target_id = ? AND active = 1",
                (target.logical_target_id,)).fetchone()
            if busy:
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

    # ------------------------------------------------------------------
    def save_job(self, job: PatchJob) -> PatchJob:
        """Persiste el estado del job y libera el lock si es terminal."""
        with self.transaction() as conn:
            conn.execute(
                """UPDATE jobs SET provider_reference = ?, state = ?, dry_run = ?, updated_at = ?,
                                   started_at = ?, completed_at = ?, error_code = ?, error_message = ?,
                                   request_payload = ?, result_payload = ?
                   WHERE id = ?""",
                (job.provider_reference, job.state.value, int(job.dry_run), _iso(job.updated_at),
                 _iso(job.started_at), _iso(job.completed_at), job.error_code, job.error_message,
                 json.dumps(job.request_payload, ensure_ascii=False),
                 json.dumps(job.result_payload, ensure_ascii=False), job.id))
            # El lock sólo se libera con un estado terminal confirmado: los
            # estados no confirmados mantienen el objetivo ocupado.
            if job.terminal:
                conn.execute("UPDATE job_targets SET active = 0 WHERE job_id = ?", (job.id,))
        return job

    def append_event(self, job_id: str, state: JobState, message: str,
                     actor: str = "msr-platform") -> JobEvent:
        event = JobEvent(job_id=job_id, state=state.value, message=message[:2000], actor=actor)
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO job_events (job_id, state, message, actor, created_at) VALUES (?,?,?,?,?)",
                (job_id, event.state, event.message, event.actor, _iso(event.created_at)))
        return event

    def has_event(self, job_id: str, message: str) -> bool:
        """Evita duplicar eventos/logs cuando el polling repite la reconciliación."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM job_events WHERE job_id = ? AND message = ? LIMIT 1",
                (job_id, message[:2000])).fetchone()
        return row is not None

    def list_events(self, job_id: str) -> list[JobEvent]:
        with self.connection() as conn:
            return list(self._events(conn, job_id))

    # ------------------------------------------------------------------
    def get_job(self, job_id: str, with_events: bool = False) -> PatchJob | None:
        with self.connection() as conn:
            return self._job_by_id(conn, job_id, with_events)

    def get_job_by_idempotency_key(self, key: str) -> PatchJob | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT job_id FROM idempotency_keys WHERE key = ?", (key,)).fetchone()
            return self._job_by_id(conn, row["job_id"], with_events=True) if row else None

    def list_jobs_for_task(self, task_id: str, limit: int = 50) -> list[PatchJob]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE task_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (task_id, limit)).fetchall()
            return [self._row_to_job(conn, r) for r in rows]

    @staticmethod
    def _active_placeholders() -> tuple[str, tuple[str, ...]]:
        states = tuple(s.value for s in sorted(ACTIVE_STATES, key=lambda s: s.value))
        return ",".join("?" for _ in states), states

    def active_job_for_task(self, task_id: str) -> PatchJob | None:
        placeholders, states = self._active_placeholders()
        with self.connection() as conn:
            row = conn.execute(
                f"SELECT * FROM jobs WHERE task_id = ? AND state IN ({placeholders}) "
                "ORDER BY created_at DESC, id DESC LIMIT 1", (task_id, *states)).fetchone()
            return self._row_to_job(conn, row, with_events=True) if row else None

    def active_job_for_target(self, logical_target_id: str) -> PatchJob | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT job_id FROM job_targets WHERE logical_target_id = ? AND active = 1 LIMIT 1",
                (logical_target_id,)).fetchone()
            return self._job_by_id(conn, row["job_id"], with_events=True) if row else None

    def list_active_jobs(self) -> list[PatchJob]:
        placeholders, states = self._active_placeholders()
        with self.connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs WHERE state IN ({placeholders}) ORDER BY created_at",
                states).fetchall()
            return [self._row_to_job(conn, r) for r in rows]

    def list_jobs_for_task_chronological(self, task_id: str) -> list[PatchJob]:
        """Orden de creación ascendente: base del *replay* de rehidratación."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE task_id = ? ORDER BY created_at, id", (task_id,)).fetchall()
            return [self._row_to_job(conn, r) for r in rows]

    def tasks_with_jobs(self) -> list[str]:
        with self.connection() as conn:
            return [r["task_id"] for r in conn.execute(
                "SELECT DISTINCT task_id FROM jobs ORDER BY task_id")]

    # --- verificaciones humanas (puertas HITL) --------------------------
    def save_verification(self, task_id: str, key: str, payload: dict) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO hitl_verifications (task_id, verification_key, payload, "
                "created_at) VALUES (?, ?, ?, ?) ON CONFLICT(task_id, verification_key) "
                "DO UPDATE SET payload = excluded.payload, created_at = excluded.created_at",
                (task_id, key, json.dumps(payload),
                 _iso(datetime.now(timezone.utc))))

    def verifications_for_task(self, task_id: str) -> dict[str, dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT verification_key, payload FROM hitl_verifications "
                "WHERE task_id = ?", (task_id,)).fetchall()
        return {r["verification_key"]: json.loads(r["payload"]) for r in rows}

    def delete_verifications(self, task_id: str, keys: list[str]) -> None:
        if not keys:
            return
        placeholders = ",".join("?" * len(keys))
        with self.transaction() as conn:
            conn.execute(
                f"DELETE FROM hitl_verifications WHERE task_id = ? "
                f"AND verification_key IN ({placeholders})", (task_id, *keys))

    # --- laboratorio reutilizable --------------------------------------
    def upsert_lab_target(self, lab: LabTarget) -> LabTarget:
        lab.updated_at = datetime.now(timezone.utc)
        with self.connection() as conn:
            self._upsert_lab(conn, lab)
        return lab

    @staticmethod
    def _upsert_lab(conn: sqlite3.Connection, lab: LabTarget) -> None:
        values = {
            "logical_lab_id": lab.logical_lab_id,
            "current_instance_id": lab.current_instance_id,
            "account_id": lab.account_id,
            "region": lab.region,
            "vulnerable_ami_id": lab.vulnerable_ami_id,
            "launch_template_id": lab.launch_template_id,
            "launch_template_version": lab.launch_template_version,
            "autoscaling_group_name": lab.autoscaling_group_name,
            "expected_vulnerable_package": lab.expected_vulnerable_package,
            "expected_vulnerable_version": lab.expected_vulnerable_version,
            "candidate_releasever": lab.candidate_releasever,
            "expected_fixed_kernel": lab.expected_fixed_kernel,
            "required_tags": json.dumps(lab.required_tags or {}, ensure_ascii=False),
            "last_reset_job_id": lab.last_reset_job_id,
            "previous_instance_id": lab.previous_instance_id,
            "lab_state": lab.lab_state,
            "current_kernel": lab.current_kernel,
            "advisory_applicable": (None if lab.advisory_applicable is None
                                    else int(lab.advisory_applicable)),
            "ssm_state": lab.ssm_state,
            "health_state": lab.health_state,
            "evidence_source": lab.evidence_source,
            "last_patch_job_id": lab.last_patch_job_id,
            "last_patch_execution_id": lab.last_patch_execution_id,
            "last_patch_at": _iso(lab.last_patch_at)
            if isinstance(lab.last_patch_at, datetime) else lab.last_patch_at,
            "last_reset_execution_id": lab.last_reset_execution_id,
            "reconciliation_state": lab.reconciliation_state,
            "last_reconciled_at": _iso(lab.last_reconciled_at)
            if isinstance(lab.last_reconciled_at, datetime) else lab.last_reconciled_at,
            "last_reconciliation_error": lab.last_reconciliation_error,
            "last_correlation_id": lab.last_correlation_id,
            "updated_at": _iso(lab.updated_at) if isinstance(lab.updated_at, datetime)
            else lab.updated_at,
        }
        columns = list(values)
        updates = ", ".join(f"{column} = excluded.{column}"
                            for column in columns if column != "logical_lab_id")
        conn.execute(
            f"""INSERT INTO lab_targets ({", ".join(columns)})
                VALUES ({", ".join("?" for _ in columns)})
                ON CONFLICT(logical_lab_id) DO UPDATE SET {updates}""",
            tuple(values[column] for column in columns))

    @staticmethod
    def _row_to_lab(row: sqlite3.Row) -> LabTarget:
        applicable = row["advisory_applicable"]
        return LabTarget(
            logical_lab_id=row["logical_lab_id"],
            current_instance_id=row["current_instance_id"],
            account_id=row["account_id"],
            region=row["region"],
            vulnerable_ami_id=row["vulnerable_ami_id"],
            launch_template_id=row["launch_template_id"],
            launch_template_version=row["launch_template_version"],
            autoscaling_group_name=row["autoscaling_group_name"],
            candidate_releasever=row["candidate_releasever"],
            expected_fixed_kernel=row["expected_fixed_kernel"],
            expected_vulnerable_package=row["expected_vulnerable_package"],
            expected_vulnerable_version=row["expected_vulnerable_version"],
            required_tags=json.loads(row["required_tags"] or "{}"),
            last_reset_job_id=row["last_reset_job_id"],
            previous_instance_id=row["previous_instance_id"],
            lab_state=row["lab_state"] or LAB_STATE_UNKNOWN,
            current_kernel=row["current_kernel"],
            advisory_applicable=None if applicable is None else bool(applicable),
            ssm_state=row["ssm_state"],
            health_state=row["health_state"],
            evidence_source=row["evidence_source"],
            last_patch_job_id=row["last_patch_job_id"],
            last_patch_execution_id=row["last_patch_execution_id"],
            last_patch_at=_parse(row["last_patch_at"]),
            last_reset_execution_id=row["last_reset_execution_id"],
            reconciliation_state=row["reconciliation_state"] or RECONCILE_IDLE,
            last_reconciled_at=_parse(row["last_reconciled_at"]),
            last_reconciliation_error=row["last_reconciliation_error"],
            last_correlation_id=row["last_correlation_id"],
            updated_at=_parse(row["updated_at"]))

    def get_lab_target(self, logical_lab_id: str) -> LabTarget | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM lab_targets WHERE logical_lab_id = ?", (logical_lab_id,)).fetchone()
            return self._row_to_lab(row) if row else None

    def list_lab_targets(self) -> list[LabTarget]:
        with self.connection() as conn:
            return [self._row_to_lab(r) for r in conn.execute(
                "SELECT * FROM lab_targets ORDER BY logical_lab_id")]

    def record_lab_reset(self, logical_lab_id: str, job_id: str) -> LabTarget | None:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM lab_targets WHERE logical_lab_id = ?", (logical_lab_id,)).fetchone()
            if row is None:
                return None
            lab = self._row_to_lab(row)
            lab.last_reset_job_id = job_id
            lab.updated_at = datetime.now(timezone.utc)
            self._upsert_lab(conn, lab)
        return lab

    # --- lock local de operación del laboratorio ------------------------
    def acquire_lab_lock(self, logical_lab_id: str, owner: str, holder: str,
                         operation: str, ttl_seconds: int, reason: str = "") -> bool:
        """Toma el lock local del laboratorio si está libre, caducado o es propio.

        Mismas reglas que el lock de DynamoDB: un lock caducado se reclama y el
        mismo `owner` (el `correlation_id` de la operación) puede reentrar, de
        forma que la reconciliación pueda lanzar su propio reset.
        """
        now = datetime.now(timezone.utc)
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM lab_locks WHERE logical_lab_id = ?",
                               (logical_lab_id,)).fetchone()
            if row is not None:
                expires = _parse(row["expires_at"])
                fresh = expires is not None and expires > now
                if fresh and row["correlation_id"] != owner:
                    return False
                conn.execute("DELETE FROM lab_locks WHERE logical_lab_id = ?",
                             (logical_lab_id,))
            conn.execute(
                """INSERT INTO lab_locks (logical_lab_id, holder, correlation_id, reason,
                                          operation, acquired_at, expires_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (logical_lab_id, holder, owner, reason, operation, _iso(now),
                 _iso(now + timedelta(seconds=max(1, ttl_seconds)))))
        return True

    def release_lab_lock(self, logical_lab_id: str, owner: str) -> bool:
        """Libera el lock sólo si lo tiene el mismo `owner`."""
        with self.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM lab_locks WHERE logical_lab_id = ? AND correlation_id = ?",
                (logical_lab_id, owner))
            return cursor.rowcount > 0

    def get_lab_lock(self, logical_lab_id: str) -> dict | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM lab_locks WHERE logical_lab_id = ?",
                               (logical_lab_id,)).fetchone()
        if row is None:
            return None
        return {"logical_lab_id": row["logical_lab_id"], "lab_id": row["logical_lab_id"],
                "holder": row["holder"], "owner": row["correlation_id"],
                "correlation_id": row["correlation_id"], "reason": row["reason"],
                "operation": row["operation"],
                "acquired_at": row["acquired_at"], "expires_at": row["expires_at"]}

    def clear(self) -> None:
        """Sólo para `POST /api/reset` y para los tests: vacía el histórico.

        `lab_targets` es configuración del laboratorio, no histórico: sobrevive
        deliberadamente al reset para poder repetir la PoC sin re-registrarlo.
        """
        with self.transaction() as conn:
            for table in ("idempotency_keys", "job_events", "job_targets", "jobs"):
                conn.execute(f"DELETE FROM {table}")
