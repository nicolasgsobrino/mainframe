# Fase 1.2 — Hardening de concurrencia, credenciales y CI

Continuación de [`IMPLEMENTATION_REPORT_PHASE1.md`](IMPLEMENTATION_REPORT_PHASE1.md) y
[`IMPLEMENTATION_REPORT_PHASE1_1.md`](IMPLEMENTATION_REPORT_PHASE1_1.md).

**No se ha ejecutado ninguna operación contra una cuenta AWS** (ni de lectura ni mutativa):
todos los tests inyectan clientes `botocore.stub.Stubber` o dobles locales. Los valores por
defecto siguen siendo `MSR_PATCH_PROVIDER=mock`, `MSR_RESTORE_PROVIDER=mock` y
`MSR_DRY_RUN=true`.

## 1. Resumen ejecutivo

| # | Problema | Corrección |
|---|----------|------------|
| 1 | Una única conexión SQLite con `check_same_thread=False` compartida entre requests, polling, reconciliador y `asyncio.to_thread` | Conexión **por operación** con WAL, `busy_timeout` y transacciones `BEGIN IMMEDIATE` |
| 2 | Los clientes EC2/SSM se cacheaban indefinidamente aunque STS renovase las credenciales | Caché invalidada por **generación de credenciales**; los clientes inyectados nunca se sustituyen |
| 3 | El reconciliador podía arrastrar estado obsoleto y morir ante un fallo transitorio | Cada tick relee lo persistido; los fallos se anotan sanitizados y aplican *backoff* acotado |
| 4 | No había prueba de reinicio real del proceso | Test de integración con fichero SQLite temporal, cierre completo y rehidratación |
| 5 | `npm ci` limpio rompía el lint (`Cannot find native binding`) | Causa identificada (Node < 22.12) y fijada con `.nvmrc` + CI |
| 6 | Tres PR encadenadas sin una vista revisable | Una única PR consolidada contra `main` |

## 2. Concurrencia SQLite

### 2.1 Problema

`JobRepository` abría **una** conexión en el constructor
(`sqlite3.connect(..., check_same_thread=False)`) y la reutilizaba en todos los métodos. Esa
conexión la usaban a la vez los handlers de FastAPI, el polling del frontend, el reconciliador
periódico y las llamadas al provider desde `asyncio.to_thread`. Con una base en fichero eso
expone a: transacciones entrelazadas (`cannot start a transaction within a transaction`),
`ProgrammingError` por uso entre hilos y cursores compartidos.

### 2.2 Solución implementada (`backend/app/repository.py`)

- `connection()` es un *context manager* que entrega una conexión de uso exclusivo para la
  operación y la cierra al terminar.
- `transaction()` envuelve toda escritura en `BEGIN IMMEDIATE` + `COMMIT` / `ROLLBACK`.
- Cada conexión configura `foreign_keys = ON`, `journal_mode = WAL` (fichero),
  `busy_timeout = 5000` y `timeout = 5` en `connect()`.
- Los conversores de filas (`_row_to_job`, `_job_by_id`, `_row_to_lab`) reciben la conexión
  de la operación en curso: ya no hay lecturas sobre una conexión ajena.
- `record_lab_reset()` lee y actualiza el laboratorio dentro de una sola transacción.
- La idempotencia (`idempotency_keys`) y el lock por objetivo (índice único parcial
  `ux_active` sobre `job_targets`) se resuelven **dentro** de la transacción; el conflicto se
  traduce a `TargetBusyError`.
- El lock sólo se libera cuando el job alcanza un estado terminal (`save_job`), incluidos los
  estados no confirmados de la fase 1.1, que **no** son terminales.

### 2.3 Bases en fichero

Cada operación abre y cierra su conexión. Consecuencia deliberada: `close()` no invalida las
operaciones posteriores (cubierto por
`test_file_repository_keeps_working_after_close`), y varios procesos/hilos pueden leer en
paralelo gracias a WAL mientras las escrituras se serializan con `BEGIN IMMEDIATE`.

### 2.4 Base `:memory:`

Con `:memory:` no es posible abrir conexiones nuevas (cada una sería otra base distinta), así
que se mantiene **una** conexión compartida protegida por un `threading.RLock`: `connection()`
la entrega bajo el guard, de modo que ninguna operación se solapa. `close()` marca el
repositorio como cerrado y cualquier uso posterior falla de forma explícita
(`RuntimeError`) en lugar de corromper estado. No se usa `check_same_thread=False` como único
mecanismo: la exclusión es explícita.

## 3. Renovación de credenciales STS y ciclo de vida de los clientes

`backend/app/providers/aws_ssm_automation.py`:

- `_assume_role_credentials()` incrementa `_credentials_generation` cada vez que STS entrega
  credenciales nuevas (renovación con margen de 60 s antes de la expiración).
- `_service_client(service)` refresca las credenciales antes de cada operación y, si la
  generación cambió, **descarta** los clientes cacheados y los reconstruye con la sesión
  vigente. Cubre `validate_target`, `start`, `poll` y `cancel`, tanto del patch provider como
  del restore provider, y por tanto también al reconciliador.
- Los clientes pasados por constructor (`ssm_client`, `ec2_client`) se guardan aparte
  (`_injected_ssm`, `_injected_ec2`) y nunca se sustituyen: los tests siguen funcionando sin
  boto3 real.
- El cliente STS se mantiene separado y usa la cadena de credenciales base.
- Las credenciales temporales no se persisten, no se registran y no aparecen en eventos ni en
  mensajes de error (los fallos de `AssumeRole` se clasifican con `classify_error`).

## 4. Reconciliador (`backend/app/reconciler.py`)

- Cada tick llama a `Store.reconcile_active_jobs()`, que relee de SQLite los jobs activos: no
  se conservan conexiones ni objetos `PatchJob` entre iteraciones.
- La exclusión por `job_id` del `Store` sigue impidiendo polling concurrente del mismo job.
- Un fallo transitorio ya no puede tumbar el bucle: se cuenta en `consecutive_failures`, se
  guarda un `last_error` **sanitizado** (`sanitize_text`), se registra un warning y el
  siguiente ciclo espera con *backoff* lineal acotado (hasta 8 × el intervalo).
- `stop()` cancela la tarea y espera su finalización desde el *lifespan* de FastAPI.
- El reconciliador no crea ejecuciones nuevas ni aplica el parche localmente.

## 5. Tests añadidos

`backend/tests/test_repository_concurrency.py` (9 tests):

- WAL y `busy_timeout` efectivos en cada conexión;
- lecturas paralelas (8 hilos × 25 iteraciones) sin corrupción;
- 8 hilos compitiendo por el mismo objetivo: un único ganador y `TargetBusyError` en el resto;
- objetivos distintos no se bloquean entre sí;
- idempotencia bajo concurrencia: una sola creación, todos ven el mismo job;
- reconciliador y API leyendo/actualizando a la vez, con los locks intactos después;
- ausencia de errores de SQLite (transacción anidada, uso entre hilos, *database is locked*);
- `:memory:` con conexión compartida protegida y cierre explícito;
- el repositorio en fichero sigue operativo tras `close()`.

`backend/tests/test_credentials_renewal.py` (6 tests): primer `AssumeRole`, clientes creados
con las primeras credenciales, avance del reloj más allá del margen, segundo `AssumeRole`,
clientes nuevos con las credenciales nuevas, no reutilización del cliente anterior, ausencia
de secretos en logs/errores y clientes inyectados sin boto3.

`backend/tests/test_restart_integration.py` (3 tests): reinicio completo (fichero temporal,
cierre de `Store` y `Repository`, instancias nuevas, rehidratación) verificando estado del
job, eventos, `rings_done`, evidencia, estado de tarea y del Vulnerable Item, ausencia de
locks huérfanos y arranque del anillo siguiente; independencia del `rings_done` aleatorio de
la línea base; y supervivencia del lock de un job aún activo.

## 6. CI (`.github/workflows/msr-platform-ci.yml`)

Único fichero fuera de `msr-platform/`, solicitado explícitamente. Se dispara en *pull
requests* y en *pushes* que toquen `msr-platform/**`. Dos jobs sin credenciales AWS y con
`MSR_DRY_RUN=true`:

- **backend**: `pip install -r requirements.txt -r requirements-dev.txt`, `pytest`, 5 pasadas
  extra de los tests de concurrencia, `ruff check app tests`, `python -m compileall app tests`.
- **frontend**: `npm ci`, comprobación del binario nativo de oxlint, `npm run lint`,
  `npx tsc -b`, `npm run build`.

**Causa real del fallo de `npm ci` + lint**: `oxlint` declara sus binarios nativos como
dependencias opcionales con `engines: ^20.19.0 || >=22.12.0`; con Node 20.18 npm los omite y
`oxlint` aborta con `Cannot find native binding`. La corrección reproducible es fijar la
versión de Node (`msr-platform/frontend/.nvmrc` → `22`, consumido por `setup-node` mediante
`node-version-file`), no instalar el binding a mano.

## 7. Resultado exacto de las validaciones

Ejecutadas desde cero (entorno limpio: `pip install -r requirements.txt -r
requirements-dev.txt`, `rm -rf node_modules && npm ci` con Node 22.12.0).

| Comando | Directorio | Resultado |
|---------|-----------|-----------|
| `pytest` | `backend` | `154 passed in 5.13s` (exit 0) |
| `ruff check app tests` | `backend` | `All checks passed!` (exit 0) |
| `python -m compileall app tests` | `backend` | exit 0 |
| `npm ci` | `frontend` | exit 0 (Node 22.12.0; binding `@oxlint/binding-linux-x64-gnu` presente) |
| `npm run lint` | `frontend` | exit 0, 8 warnings preexistentes (`react(only-export-components)` en `src/ui.tsx`) |
| `npx tsc -b` | `frontend` | exit 0 |
| `npm run build` | `frontend` | exit 0; `dist/assets/index-*.js 831.07 kB`, con el aviso preexistente de chunk > 500 kB |

Ejecuciones repetidas de concurrencia:

- `pytest tests/test_repository_concurrency.py -x` × **20 pasadas**: 20/20 en verde, 0 fallos
  (`pasadas=20 fallos=0`);
- `pytest tests/test_repository_concurrency.py tests/test_restart_integration.py
  tests/test_credentials_renewal.py -x` × **10 pasadas**: 18 tests en verde en cada pasada.

No se instaló `pytest-repeat`: las repeticiones se hicieron con un bucle de shell comprobando
el código de salida de cada pasada.

## 7.bis Fallo observado en GitHub Actions y corrección

Los resultados locales de arriba estaban en verde, pero la primera ejecución **real** del CI
sobre el commit `ba57fc2` no lo estuvo:

| Ejecución | Job | Resultado |
|-----------|-----|-----------|
| `pull_request` run [30990085743](https://github.com/nicolasgsobrino/mainframe/actions/runs/30990085743) | backend / frontend | verdes |
| `push` run [30990085742](https://github.com/nicolasgsobrino/mainframe/actions/runs/30990085742) | frontend | verde |
| `push` run [30990085742](https://github.com/nicolasgsobrino/mainframe/actions/runs/30990085742) | backend job `92253886900` | **fallo, exit code 1** |

Traceback del CI:

```text
FAILED tests/test_api.py::test_idempotency_key_replays_instead_of_conflicting
    assert replay.json()["active_job"]["id"] == first.json()["active_job"]["id"]
E   TypeError: 'NoneType' object is not subscriptable
1 failed, 153 passed in 6.60s
```

**Causa raíz** (no es un fallo transitorio del runner ni un defecto del código de producción,
sino una dependencia del reloj de pared en los tests): la *fixture* `client` de
`tests/test_api.py` fijaba `MSR_MOCK_JOB_DURATION_SECONDS=1`. El provider mock termina el job
cuando han pasado esos segundos, y `task_detail` devuelve `active_job = null` para un job ya
terminal. Si el runner tarda más de 1 s entre el primer `POST /approve` y su repetición con la
misma `Idempotency-Key`, el replay —correcto: sigue devolviendo `202` y el mismo job— llega
cuando el job ya ha terminado y `active_job` es `null`. La misma carrera afectaba a los demás
tests de `test_api.py` y a los que usan la *fixture* `settings` con duración 1 s.

Reproducción determinista en local (mismo entorno: Ubuntu, Python 3.10, dependencias de
`requirements*.txt`, `MSR_PATCH_PROVIDER=mock`, `MSR_DRY_RUN=true`), insertando la lentitud del
runner entre las dos peticiones:

```text
MSR_MOCK_JOB_DURATION_SECONDS=1 + sleep 1.2 s  ->  replay 202, active_job: None   (fallo del CI)
MSR_MOCK_JOB_DURATION_SECONDS=600 + sleep 3 s  ->  replay 202, mismo job id       (corregido)
```

**Corrección**: la duración del job mock pasa a 600 s en `tests/conftest.py` y en la *fixture*
`client` de `tests/test_api.py`. Los tests que necesitan un job terminado no dependen de ese
valor: usan un reloj congelado (`FrozenClock`) o fijan su propia duración. No se ha eliminado
ni marcado como *skip* ningún test, no se han añadido reintentos y no se ha relajado ninguna
aserción ni la concurrencia: sólo se elimina la dependencia del reloj de pared.

Resultados reales del CI tras la corrección: ver la sección 11.

## 8. Archivos

Creados:

- `msr-platform/backend/tests/test_repository_concurrency.py`
- `msr-platform/backend/tests/test_credentials_renewal.py`
- `msr-platform/backend/tests/test_restart_integration.py`
- `msr-platform/frontend/.nvmrc`
- `msr-platform/IMPLEMENTATION_REPORT_PHASE1_2.md`
- `.github/workflows/msr-platform-ci.yml`

Modificados:

- `msr-platform/backend/app/repository.py`
- `msr-platform/backend/app/providers/aws_ssm_automation.py`
- `msr-platform/backend/app/reconciler.py`
- `msr-platform/frontend/src/types.ts`
- `msr-platform/README.md`
- `msr-platform/backend/tests/conftest.py` y `msr-platform/backend/tests/test_api.py` (duración
  del job mock: se elimina la dependencia del reloj de pared que hizo fallar el CI)

## 9. Riesgos y limitaciones

- El *backoff* del reconciliador es lineal y acotado; no hay circuit breaker ni métricas.
- SQLite sigue siendo adecuado para un único proceso backend: con varias réplicas haría falta
  un motor con locks distribuidos (el índice único parcial protege el objetivo, pero WAL no
  sustituye a una base compartida real).
- La renovación de credenciales se comprueba al obtener el cliente, no durante una llamada ya
  en curso: una operación larga puede seguir viendo `ExpiredToken` y se reintentará en el
  ciclo siguiente.
- Los runbooks `MSR-*` todavía no existen en ninguna cuenta: `describe_document` fallará en
  cuanto se pase a modo real.
- No se ha implementado la destrucción/recreación real del laboratorio ni Terraform.
- El CI no ejecuta ningún escenario contra AWS ni define secretos.

## 10. Confirmaciones

- **Ninguna llamada a AWS** durante el desarrollo ni durante los tests: `boto3` se importa de
  forma perezosa y los clientes se inyectan (`Stubber` o dobles locales).
- `MSR_DRY_RUN=true`, `MSR_PATCH_PROVIDER=mock` y `MSR_RESTORE_PROVIDER=mock` siguen siendo
  los valores por defecto, también en CI.
- No se han añadido credenciales, `.env` reales, bases SQLite generadas ni recursos AWS.

## 11. Resultados reales del CI (tras la corrección)

Commit de la corrección: `7c91fe0`. Los cuatro checks requeridos terminaron en verde:

| Check | Run | Job | Resultado |
|-------|-----|-----|-----------|
| `push / backend` | [30991333701](https://github.com/nicolasgsobrino/mainframe/actions/runs/30991333701) | `92257938177` | success |
| `push / frontend` | [30991333701](https://github.com/nicolasgsobrino/mainframe/actions/runs/30991333701) | `92257938190` | success |
| `pull_request / backend` | [30991339311](https://github.com/nicolasgsobrino/mainframe/actions/runs/30991339311) | `92257957163` | success |
| `pull_request / frontend` | [30991339311](https://github.com/nicolasgsobrino/mainframe/actions/runs/30991339311) | `92257957102` | success |

Validaciones locales repetidas con la corrección aplicada: `pytest` 154 passed,
`ruff check app tests` sin hallazgos, `compileall` exit 0, concurrencia 20/20 pasadas y
reinicio + renovación de credenciales 10/10 pasadas, todas sin fallos.

PR consolidada: <https://github.com/nicolasgsobrino/mainframe/pull/6>.
