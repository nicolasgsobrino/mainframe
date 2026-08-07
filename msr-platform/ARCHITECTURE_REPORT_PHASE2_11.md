# Fase 2.11 — Arranque de MSR en la sesión de Devin y bootstrap único de AWS

Arquitectura final aprobada en la fase 2.10:

```text
usuario autorizado de la organización
  → sesión de Devin  → VM de la sesión  → MSR (FastAPI + React) en :8080
  → identidad de workload OIDC de Devin
  → sts:AssumeRoleWithWebIdentity  → MSRExternalBackendRole
  → SSM Automation  → EC2 Linux del laboratorio
```

AWS aloja **sólo** el laboratorio de parcheo y los recursos mínimos de control que
necesita. No se requiere ninguna URL pública: la superficie oficial de la demo es la
pestaña **Desktop** de la sesión.

**Ninguna mutación en AWS en esta fase**: no se ha creado el proveedor OIDC, ni el rol, ni la
tabla de locks, ni se ha ejecutado ningún patch o reset.

---

## 1. El `sub` del token ya está resuelto (sin depender del administrador)

Se instaló el intercambio de token de la sesión y se decodificó el JWT **en local**, sin
imprimirlo, persistirlo ni publicarlo. Sólo el resultado:

```text
iss     https://deloitte-es.devinenterprise.com
aud     sts.amazonaws.com
sub     org_id:org-4793cba689a54a11b8fe70ed031524c4
org_id  org-4793cba689a54a11b8fe70ed031524c4
```

Mecanismo verificado (documentado en `setup-devin-oidc`): el token general de la sesión está
en `/opt/.devin/oidc_token` y se intercambia por uno con audiencia acotada mediante
`POST {iss}/api/oidc/token` (RFC 8693 token exchange, `subject_keys=org_id`). La respuesta fue
HTTP 200 y el token resultante llevaba exactamente los valores de arriba.

Consecuencia: **la trust policy del §3.2 es literal y ya no hay dependencia del administrador
de Devin** para obtener el org ID. Nótese que el sujeto **sí** incluye el prefijo `org-`
(`org_id:org-…`), a diferencia del ejemplo de la documentación.

---

## 2. Separación de responsabilidades

| | ONE-TIME AWS BOOTSTRAP | REPEATABLE DEVIN SESSION STARTUP |
|---|---|---|
| Quién | Equipo de cloud, una vez | Cualquier usuario autorizado, cada demo |
| Dónde | Cuenta `133789123239` | VM de la sesión de Devin |
| Qué | Proveedor OIDC, `MSRExternalBackendRole`, tabla de locks, runbooks | `scripts/start_poc.sh` |
| Frecuencia | Una vez (y su Terraform) | Cada sesión y cada vez que la sesión despierta |
| Requiere autorización | **Sí** (pendiente) | No: es de sólo lectura y `MSR_DRY_RUN=true` |

---

## 3. ONE-TIME AWS BOOTSTRAP

Nada de esta sección se ha ejecutado. Recordatorio de la fase 2.7: la cuenta deniega
(`explicitDeny`) `iam:PutRolePolicy` e `iam:AttachRolePolicy`, así que **el rol lo crea el
equipo de cloud**, no este Terraform.

### 3.1 Proveedor OIDC de IAM

| Campo | Valor |
|---|---|
| Provider URL | `https://deloitte-es.devinenterprise.com` |
| Audience (client ID) | `sts.amazonaws.com` |
| Firma | RS256, JWKS en `https://deloitte-es.devinenterprise.com/.well-known/jwks.json` |
| ARN resultante | `arn:aws:iam::133789123239:oidc-provider/deloitte-es.devinenterprise.com` |

### 3.2 Trust policy exacta de `MSRExternalBackendRole`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "OnlyDevinSessionsOfThisOrgMayAssumeThisRole",
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::133789123239:oidc-provider/deloitte-es.devinenterprise.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "deloitte-es.devinenterprise.com:aud": "sts.amazonaws.com",
          "deloitte-es.devinenterprise.com:sub": "org_id:org-4793cba689a54a11b8fe70ed031524c4"
        }
      }
    }
  ]
}
```

Sin comodines: sólo sesiones de esta organización, sólo con esa audiencia. Las credenciales
son temporales (1 h) y el helper de Devin las renueva, así que no hay nada que rotar ni
revocar; para cortar el acceso basta con borrar el rol o el proveedor.

### 3.3 Política de permisos exacta

Es la que ya genera Terraform, sin cambios: el output
`backend_task_role_permission_policy_json` de `infra/terraform/backend_iam.tf`. Contenido
funcional:

- `ec2:DescribeInstances`, `ec2:DescribeTags`, `ec2:DescribeInstanceStatus` — descubrimiento
  por tags y validación de cuenta/región/entorno (no hay Instance ID en la configuración).
- `ssm:DescribeInstanceInformation`, `ssm:StartAutomationExecution`,
  `ssm:GetAutomationExecution`, `ssm:DescribeAutomationStepExecutions`,
  `ssm:StopAutomationExecution`, `ssm:ListCommands`, `ssm:GetCommandInvocation` — parcheo y
  seguimiento, acotado a los tres runbooks MSR.
- `autoscaling:DescribeAutoScalingGroups`, `autoscaling:DescribeScalingActivities`,
  `autoscaling:TerminateInstanceInAutoScalingGroup` — reset y recuperación dentro del ASG.
- `sts:GetCallerIdentity` — verificación de identidad del arranque.
- Lock, acotado a la tabla:

```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"],
  "Resource": "arn:aws:dynamodb:eu-north-1:133789123239:table/msr-poc-lab-locks"
}
```

Sigue **sin** `iam:PassRole` (los runbooks no declaran `assumeRole`: la Automation corre con la
identidad que la inicia), sin `dynamodb:UpdateItem` y sin `dynamodb:*`.

### 3.4 Tabla de locks

`msr-poc-lab-locks`, clave de partición `lab_id`, TTL en `expires_at`, `PAY_PER_REQUEST`
(`infra/terraform/backend_locks.tf`). **Se mantiene** porque cada sesión de Devin es una VM con
disco propio y dos personas pueden abrir dos sesiones contra el mismo laboratorio: un lock en
SQLite no serializa nada entre sesiones. Cubre patch real, reset real y reconciliación
destructiva.

### 3.5 Blueprint del repositorio

Configuración única en Devin (hoy el repositorio **no tiene blueprint**, verificado). Propuesta
enviada como sugerencia para su aprobación:

```yaml
initialize:
  - uses: github.com/CognitionAI/actions/setup-aws-oidc@main
    with:
      role-arn: "arn:aws:iam::133789123239:role/MSRExternalBackendRole"
      region: "eu-north-1"
maintenance: |
  (cd msr-platform/backend && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt)
  (cd msr-platform/frontend && npm install --silent)
```

La acción escribe un `credential_process` en el perfil por defecto de `~/.aws/config`: boto3
resuelve credenciales temporales por la cadena estándar del SDK y la aplicación **no**
configura perfil (`MSR_AWS_PROFILE=`) ni assume-role (`MSR_AWS_ROLE_ARN=`). No hace falta
guardar ningún secreto: el ARN del rol no es sensible.

Mientras el blueprint no esté aprobado, `scripts/start_poc.sh` instala las dependencias por sí
mismo y arranca en modo `mock` (no hay identidad de AWS) — la demo funciona simulada.

---

## 4. REPEATABLE DEVIN SESSION STARTUP

Un único comando, idempotente, repetible tras dormir o reiniciar la sesión:

```bash
msr-platform/scripts/start_poc.sh
```

Lo que hace, en orden:

1. **Dependencias** incrementales: `.venv` si falta, `pip install -r requirements.txt`,
   `npm install` si falta `node_modules`.
2. **Build de producción** de la SPA (`scripts/build.sh` → `backend/static`), y **sólo** si
   falta o hay fuentes más recientes que el build.
3. **Configuración** por variables de entorno, sin `.env`: región, runbooks, ASG
   (`msr-poc-<lab-id>-asg`), `MSR_DRY_RUN=true`, `MSR_LAB_RECONCILE_ON_STARTUP=false`,
   `MSR_AWS_PROFILE=""`, `MSR_AWS_ROLE_ARN=""`. Ningún valor es un secreto.
4. **Verificación de identidad de AWS**: `python -m app.identity_check`, que llama sólo a
   `sts:GetCallerIdentity` y comprueba que la cuenta está en la allowlist. Imprime cuenta, ARN
   y origen de las credenciales; nunca una credencial.
   - con identidad → `aws-automation` + allowlist fail-closed (`133789123239`, `eu-north-1`,
     `sandbox`) y `MSR_DRY_RUN=true`;
   - sin identidad → `mock`, y la demo sigue funcionando;
   - `MSR_POC_MODE=aws` fuerza el modo AWS y **falla** si no hay identidad.
5. **Backend** en `127.0.0.1:8080` (reinicio idempotente: mata el uvicorn anterior de ese
   puerto), espera activa del health y volcado de `/api/health` y `/api/execution`.
6. **Laboratorio, comprobación no destructiva**: `python -m app.lab_hook` **sin** `--confirm`
   → descubre la instancia por tags, valida cuenta/región/tags e informa. Nunca resetea. Si el
   laboratorio no está listo, lo dice y deja la aplicación arriba.
7. **Instrucciones**: abrir `http://localhost:8080` en el navegador de la VM y operar desde la
   pestaña Desktop.

Verificado en esta sesión (modo `mock`, sin credenciales de AWS): exit 0, `/api/health` → 200,
SPA → 200, `app.lab_hook` → `ready: true`, y una segunda ejecución reutilizó el build
(`Frontend ya compilado`) y reinició el backend sin duplicarlo.

### 4.1 Recuperación tras dormir/reiniciar

La sesión conserva el disco pero **no** los procesos (verificado en la fase 2.10). La
recuperación es volver a ejecutar el mismo comando: las dependencias y el build ya están, así
que sólo se relanza el backend y se revalida el laboratorio.

### 4.2 Lo que el usuario no necesita

Ni instalación local, ni `aws login`, ni perfil de AWS, ni claves estáticas, ni Instance ID, ni
`.env`, ni nombres de runbooks, ni la CLI de AWS. Sólo pedirle a Devin que arranque la PoC.

Playbook/knowledge asociado: `msr-platform/PLAYBOOK_START_POC.md`, para que «arranca la PoC de
MSR» sea suficiente.

---

## 5. Seguridad: lo que sigue exigiendo autorización explícita

| Operación | Cómo se autoriza |
|---|---|
| Patch real | `MSR_DRY_RUN=false` explícito (el arranque nunca lo pone) |
| Reset destructivo | `python -m app.lab_hook --confirm`, con lock de DynamoDB |
| Reconciliación en arranque | `MSR_LAB_RECONCILE_ON_STARTUP` fijado a `false` por el script |
| Mutar el laboratorio en paralelo | Imposible: el lock admite una sola operación a la vez |

Tests que lo fijan (`backend/tests/test_session_startup.py`): el script no contiene ninguna
credencial ni `aws configure`/`aws login`, no fija ningún Instance ID, no lee ni copia un
`.env`, mantiene `MSR_DRY_RUN=true` y `MSR_LAB_RECONCILE_ON_STARTUP=false`, nunca invoca
`app.lab_hook --confirm`, verifica la identidad **antes** de activar los providers de AWS y es
idempotente; y una sesión limpia arranca en `mock`, `dry_run=true`, sin perfil ni rol.

---

## 6. Corrección de un defecto encontrado al implementarlo

Configurar la allowlist desde el entorno con un solo valor
(`MSR_ALLOWED_REGIONS=eu-north-1`) **rompía el arranque**: pydantic-settings intentaba
decodificarlo como JSON antes de aplicar el validador CSV
(`SettingsError: error parsing value for field "allowed_regions"`). Los campos de lista pasan a
`Annotated[list[str], NoDecode]`, de modo que CSV y JSON funcionan. Sin esta corrección, el
arranque fail-closed contra AWS era imposible sin fichero `.env`.

---

## 7. Estado y autorizaciones pendientes

| Elemento | Estado |
|---|---|
| `sub` del token OIDC | **Resuelto y verificado** |
| Trust policy y política de permisos | Escritas, listas para aplicar |
| Script de arranque idempotente | Implementado y probado en modo mock |
| Tests de sesión limpia | Implementados |
| Blueprint con `setup-aws-oidc` | Propuesto, pendiente de aprobación |
| Proveedor OIDC, `MSRExternalBackendRole`, tabla de locks | **Pendientes de autorización** (ninguna mutación hecha) |
| Arranque en modo `aws` verificado de punta a punta | Pendiente: requiere el bootstrap anterior |
| Patch/reset reales | Pendientes de autorización explícita |
