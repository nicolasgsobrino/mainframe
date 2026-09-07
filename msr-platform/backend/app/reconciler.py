"""Reconciliador periódico de jobs activos.

El ejecutor duradero sigue siendo el proveedor (AWS Systems Manager Automation o
el mock): este componente **no** crea ejecuciones ni aplica parches. Sólo lee de
SQLite los jobs activos, llama a `provider.poll()` a través del store y persiste
el resultado, de modo que el estado avanza aunque nadie tenga la UI abierta.

El `Store` garantiza que un mismo job no se consulta en paralelo (lock por job),
por lo que el reconciliador y el polling del frontend pueden coexistir.

Cada pasada relee el estado persistido y no conserva conexiones SQLite ni objetos
`PatchJob` entre iteraciones. Un fallo transitorio no termina el bucle: se anota
un error sanitizado y se espera con *backoff* acotado hasta el siguiente ciclo.
"""
from __future__ import annotations

import asyncio
import logging

from .policy import sanitize_text

log = logging.getLogger("msr.reconciler")

MAX_BACKOFF_MULTIPLIER = 8


class JobReconciler:
    """Tarea asíncrona cancelable, gobernada por el lifespan de FastAPI."""

    def __init__(self, store, interval_seconds: int, enabled: bool = True):
        self._store = store
        self.interval_seconds = max(1, int(interval_seconds))
        self.enabled = enabled
        self._task: asyncio.Task | None = None
        self.ticks = 0
        self.last_reconciled = 0
        self.last_error: str | None = None
        self.consecutive_failures = 0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "ticks": self.ticks,
            "last_reconciled": self.last_reconciled,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
        }

    def start(self) -> None:
        if not self.enabled or self.running:
            return
        self._task = asyncio.create_task(self._loop(), name="msr-job-reconciler")
        log.info("reconciler started (every %ss)", self.interval_seconds)

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        log.info("reconciler stopped")

    async def tick(self) -> int:
        """Una pasada de reconciliación (el I/O del provider va a un hilo)."""
        reconciled = await asyncio.to_thread(self._store.reconcile_active_jobs)
        self.ticks += 1
        self.last_reconciled = reconciled
        self.last_error = None
        self.consecutive_failures = 0
        return reconciled

    def _delay(self) -> float:
        """Backoff lineal acotado tras fallos consecutivos."""
        multiplier = min(1 + self.consecutive_failures, MAX_BACKOFF_MULTIPLIER)
        return self.interval_seconds * multiplier

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._delay())
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # nunca debe tumbar el bucle
                self.consecutive_failures += 1
                # Mensaje sanitizado: nunca credenciales ni payloads completos.
                self.last_error = sanitize_text(f"{type(exc).__name__}: {exc}", 300)
                log.warning("periodic reconciliation failed (%s consecutive): %s",
                            self.consecutive_failures, self.last_error)
