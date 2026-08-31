# Fase 2.9 — MSR fuera de AWS: informe de arquitectura

**No se ha ejecutado ninguna mutación en AWS** en esta fase: ni `terraform apply`, ni plan
real, ni creación de recursos, ni cambios de IAM, ni patch, ni reset. Este documento cierra
la arquitectura objetivo antes de tocar nada.

Corrección de arquitectura aceptada: la aplicación MSR **no se aloja en AWS**. AWS queda
reducido al laboratorio de parcheo y a la ejecución de los runbooks.

```text
usuario
  → aplicación MSR alojada fuera de AWS (frontend + FastAPI)
  → APIs de AWS
  → SSM Automation (MSR-PatchLinuxInstance / MSR-ResetLabInstance)
  → EC2 del laboratorio Linux (descubierta por tags)
```

## 1. Mecanismo de despliegue realmente disponible

Evidencia recogida en esta sesión, no supuestos:

| Comprobación | Resultado |
| --- | --- |
| Documentación oficial (`docs.devin.ai/product-guides/deployment-capabilities`) | Devin despliega aplicaciones **que él mismo crea desde sus plantillas** (frontend Vite/TS/Tailwind/Shadcn y backend FastAPI). Literal: *"Pre-existing Apps: Devin is not equipped to deploy pre-existing applications. While frontend apps might work, backend apps will not in 99% of cases"*, y para aplicaciones ajenas a las plantillas *"users should choose their own deployment method and provide Devin with the necessary credentials and instructions via Secrets and Knowledge"*. |
| Herramienta de despliegue gestionado en esta sesión | **No disponible**: no existe ninguna herramienta de deploy en el conjunto de herramientas de esta sesión enterprise, y el directorio de settings del webapp no expone ninguna opción de *App deploys*. |
| `flyctl` / `fly` en la VM | No instalado. |
| Documentación de Fly.io sobre OIDC (`fly.io/docs/security/openid-connect/`) | El runtime de Fly **sí** emite tokens OIDC por máquina y AWS es un proveedor soportado (detalle en §5). |

Conclusión, sin ambigüedad: el despliegue gestionado *"pídeselo a Devin y lo despliega"*
**no está disponible** para esta aplicación tal cual está. MSR es una aplicación
preexistente (FastAPI + Vite propios, SQLite, providers AWS), no una app generada desde la
plantilla, y además el enterprise de esta cuenta no expone la herramienta de despliegue.

### Opciones reales

| | A. Fly.io con cuenta propia (recomendada) | B. Reescribir MSR sobre la plantilla de Devin | C. Sólo vista previa en la VM de Devin |
| --- | --- | --- | --- |
| Quién aloja | Fly.io, organización de Deloitte/cliente | Fly.io, gestionado por Devin | La VM de la sesión |
| URL pública | `https://<app>.fly.dev` (o dominio propio + TLS de Fly) | asignada por el servicio | ninguna: sólo la pestaña *Browser* de la sesión |
| Federación OIDC a AWS | **Sí** (§5) | Desconocida/no controlable: no se puede fijar `fly.toml` ni conocer el org slug del emisor | No |
| Persistencia | Fly Volume | Desconocida | Efímera |
| Coste de implementación | bajo: ya existe `Dockerfile` que compila la SPA y sirve `/api` | alto: reimplementar la aplicación | nulo |
| Repetible por cualquier usuario autorizado | Sí (token de Fly como secreto de organización en Devin) | Sí | No |

**Recomendación: opción A.** El artefacto ya existe (`msr-platform/Dockerfile`, imagen única
que compila el frontend y lo sirve desde FastAPI), Fly.io es exactamente el runtime que
usa el despliegue gestionado, y es el único camino que permite identidad de workload sin
credenciales estáticas. Requiere una decisión del usuario: **un token de API de Fly.io de la
organización** guardado como secreto en Devin (`FLY_API_TOKEN`) y el slug de esa
organización. Sin eso, MSR no puede alojarse fuera de AWS más que como vista previa (opción
C).

## 2. Dónde vive cada parte

Una sola aplicación, un solo proceso, un solo origen — ya es así hoy:

```text
Fly Machine (imagen msr-platform)
  ├─ FastAPI (uvicorn :8080)
  │    ├─ /api/*          API
  │    └─ /               SPA compilada (backend/static), servida por el propio backend
  └─ python -m app.lab_hook   ejecución puntual de reconciliación (release)
```

No hay CDN, ni bucket, ni frontend desplegado por separado: `scripts/build.sh` compila la
SPA en `backend/static` y el `Dockerfile` la incluye. Health check HTTP: `/api/health`.

## 3. Modelo de URL pública

- Fly asigna `https://<app-name>.fly.dev` con TLS gestionado, sin necesidad de certificado
  ni DNS corporativo (esto elimina la dependencia de ACM/DNS de la fase anterior).
- Restricción de acceso: la aplicación **no tiene autenticación propia**. Antes de publicar
  la URL hace falta decidir el control de acceso; el mínimo razonable es autenticación en el
  borde (Fly + Basic auth o Cloudflare Access/Tailscale delante) o mantener `MSR_DRY_RUN=true`
  mientras la URL sea pública. Queda como decisión abierta (§12), no la doy por resuelta.

## 4. Persistencia

El filesystem de una Fly Machine es efímero (se pierde al recrear la máquina), así que la
SQLite de jobs **no puede** quedarse en el filesystem raíz:

- Solución mínima: un **Fly Volume** montado en `/data` y `MSR_JOBS_DB_PATH=/data/msr_jobs.db`.
  Un volumen está anclado a una máquina, lo que encaja con una sola máquina para la PoC.
- El estado autoritativo del laboratorio sigue siendo **AWS** (`ensure_lab_ready` reconstruye
  la verdad desde tags, ASG, SSM y el advisory), así que perder la SQLite degrada el
  historial de jobs, no la corrección del laboratorio.
- Alternativa si se escala a varias máquinas: Postgres gestionado y sustituir el repositorio
  SQLite. No es necesario para la PoC y no lo propongo todavía.

## 5. Autenticación a AWS desde fuera de AWS

El ECS Task Role deja de ser aplicable. Diseño preferido, y **técnicamente soportado** según
la documentación de Fly.io:

```text
Fly Machine (MSR)
  → token OIDC del runtime (POST unix:/.fly/api /v1/tokens/oidc, aud=sts.amazonaws.com)
  → AWS STS AssumeRoleWithWebIdentity
  → MSRExternalBackendRole
  → SSM Automation / EC2 / Auto Scaling / DynamoDB
```

Evidencia (documentación de Fly.io, *Security → OpenID Connect*):

- Cada máquina puede pedir un JWT propio al endpoint local `/.fly/api`
  (`POST /v1/tokens/oidc`, `{"aud":"sts.amazonaws.com"}`).
- Emisor: `https://oidc.fly.io/<org-slug>`; claim `sub` con el formato
  `<org>:<app>:<machine>`; credenciales resultantes de corta duración.
- AWS figura explícitamente entre los proveedores soportados y la propia documentación
  publica el patrón de trust policy con `sts:AssumeRoleWithWebIdentity`.

Lo que **no** he podido verificar y por tanto no afirmo: si Fly rellena automáticamente
`AWS_WEB_IDENTITY_TOKEN_FILE`. El diseño no depende de ello: el backend obtiene el token él
mismo y lo escribe/renueva, que es la forma en que boto3 resuelve la federación sin código
propio de credenciales.

### 5.1 Recurso IAM a crear en AWS (proveedor OIDC + rol)

```text
OIDC provider:
  URL:      https://oidc.fly.io/<org-slug>
  Audience: sts.amazonaws.com
Rol:        MSRExternalBackendRole
```

Trust policy exacta (`<org-slug>` y `<app-name>` se fijan al crear la app; sin comodín de
organización ni de audiencia):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "OnlyTheMsrFlyAppMayAssumeThisRole",
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::133789123239:oidc-provider/oidc.fly.io/<org-slug>"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.fly.io/<org-slug>:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "oidc.fly.io/<org-slug>:sub": "<org-slug>:msr-platform:*"
        }
      }
    }
  ]
}
```

### 5.2 Política de permisos exacta

Es la misma política de mínimo privilegio ya acordada para el workload (sin `iam:PassRole`,
sin `dynamodb:UpdateItem`, sin `ec2:TerminateInstances`, sustitución sólo vía ASG). El
módulo la publica en el output `backend_task_role_permission_policy_json`; reproducida en
`PRE_APPLY_POC_DEPLOYMENT_PROFILE.md` §6.2. No cambia por alojar la aplicación fuera de AWS:
las llamadas son las mismas.

Cambia sólo lo que ya no hace falta: **desaparece el ECS execution role** (no hay agente de
ECS que descargue una imagen de ECR ni escriba en CloudWatch Logs).

### 5.3 Configuración del backend

```env
MSR_PATCH_PROVIDER=aws-automation
MSR_RESTORE_PROVIDER=aws-automation
MSR_DRY_RUN=true
MSR_LAB_RECONCILE_ON_STARTUP=false
MSR_AWS_PROFILE=
MSR_AWS_ROLE_ARN=
MSR_AWS_REGION=eu-north-1
MSR_JOBS_DB_PATH=/data/msr_jobs.db
```

`MSR_AWS_ROLE_ARN` sigue **vacío**: no se hace un `sts:AssumeRole` explícito desde la
aplicación. La federación se resuelve en la cadena de credenciales estándar de boto3 con las
variables propias del SDK:

```env
AWS_ROLE_ARN=arn:aws:iam::133789123239:role/MSRExternalBackendRole
AWS_WEB_IDENTITY_TOKEN_FILE=/tmp/fly-oidc-token
AWS_REGION=eu-north-1
```

y un renovador mínimo dentro del contenedor que reescribe ese fichero con un token fresco
(los JWT de Fly son de corta duración y boto3 relee el fichero al refrescar). Es el único
componente nuevo de código que exige esta arquitectura; `credentials_source()` seguirá
informando `default-chain`. Ninguna clave de acceso, ningún session token copiado, ningún
`aws login`, ningún perfil de desarrollador.

## 6. Si la federación no fuese soportada (fallback, no preferido)

Si al implementarlo se comprobara que la organización de Fly no puede emitir tokens OIDC (o
si se eligiera otro alojamiento sin identidad federada), **no** se cae silenciosamente a
claves permanentes. Se reportaría la limitación y el fallback se diseñaría aparte con:

- usuario IAM dedicado `msr-poc-external-backend`, exclusivo de la PoC, sin consola;
- la misma política de mínimo privilegio de §5.2, nada más;
- almacenamiento como *secret* del despliegue (`fly secrets set`) y como secreto de
  organización en Devin, nunca en el repositorio, ni en la imagen, ni en `fly.toml`;
- rotación programada (p. ej. 30 días) y rotación inmediata ante cualquier sospecha;
- radio de impacto explícito: sólo SSM Automation sobre los dos runbooks de la PoC, lectura
  de EC2/ASG, terminación **exclusivamente** a través del ASG del laboratorio y tres
  acciones sobre una única tabla DynamoDB; ninguna capacidad de crear infraestructura;
- procedimiento de retirada: borrar la access key, borrar el usuario, borrar el secreto de
  Fly y de Devin, y confirmar con `iam:GetUser`/CloudTrail que no queda uso.

## 7. Lock distribuido: decisión

**Se mantiene el lock en DynamoDB**, aunque la aplicación viva fuera de AWS.

Razones: el alojamiento externo puede ejecutar varias máquinas/procesos (escalado o despliegue
solapado, con máquinas nuevas y antiguas conviviendo unos segundos), y el hook de release es
un proceso distinto del servicio web. Con SQLite en un volumen local, dos máquinas no
comparten estado y podrían resetear el laboratorio a la vez. El lock también es el único
punto donde patch, reset y reconciliación se serializan entre sí.

- Tabla: `msr-poc-lab-locks`, partition key `lab_id`, TTL en `expires_at`.
- Adquisición: `PutItem` condicional que también trata el ítem caducado; liberación:
  `DeleteItem` condicionado al owner.
- Permisos exactos: `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:DeleteItem` sobre
  `arn:aws:dynamodb:eu-north-1:133789123239:table/msr-poc-lab-locks`. Sin `UpdateItem`, sin
  `dynamodb:*`, sin comodines de recurso.
- SQLite sigue disponible sólo para `mock`/`aws-dry-run` y desarrollo local.

## 8. Qué queda en AWS

1. EC2 del laboratorio + Launch Template + Auto Scaling Group (1/1/1).
2. Security group del laboratorio y sus reglas de salida.
3. Patch baseline + patch group.
4. `MSR-PatchLinuxInstance` y `MSR-ResetLabInstance` (documentos Automation).
5. Integración de nodo gestionado por SSM (instance profile corporativo existente, sólo lectura).
6. `msr-poc-lab-locks` (DynamoDB).
7. Identidad para el backend externo: proveedor OIDC + `MSRExternalBackendRole` (§5.1), o el
   usuario IAM del fallback (§6).

Nada de esto aloja la aplicación.

## 9. Qué se retira del diseño ECS anterior

Marcado como **superseded / no objetivo** (código conservado por valor histórico, pero
desactivado por defecto y sin que ningún despliegue dependa de él):

| Componente | Estado |
| --- | --- |
| `aws_ecs_cluster` / `aws_ecs_task_definition` / `aws_ecs_service` | superseded (`enable_backend_service = false`) |
| `aws_ecr_repository` / `aws_ecr_lifecycle_policy` | superseded (`enable_backend_ecr = false`) |
| ALB, target group, listeners y sus security groups | superseded (`enable_backend_alb = false`) |
| ECS Task Role / ECS execution role (ARNs externos) | superseded: sustituidos por `MSRExternalBackendRole` federado |
| CloudWatch log group del contenedor | superseded: los logs los da el alojamiento externo |
| `backend_alb_ingress_cidrs`, subnets del ALB, subnets de ECS, `assign_public_ip`, certificado ACM | **ya no son bloqueantes y no se piden al equipo de red** |

`msr-platform/Dockerfile` **no** se retira: la imagen (frontend compilado + FastAPI + hook)
es exactamente el artefacto que necesita el alojamiento externo.

## 10. Trabajo de laboratorio que se conserva íntegro

Descubrimiento dinámico de la EC2 por tags, `ensure_lab_ready`, validación *fail-closed* de
cuenta/región/tags, los tres modos (`mock` / `aws-dry-run` / `aws-real`), sincronización de
patch/reset con el estado real y AWS como fuente de verdad operativa. Nada de esto depende
de dónde se aloje la aplicación.

## 11. Flujo repetible «Deploy MSR»

Objetivo: la identidad AWS pertenece al servicio desplegado, no a la persona que pide el
despliegue.

```text
usuario autorizado
  → «despliega MSR»
  → Devin: build de la imagen y `fly deploy` con el FLY_API_TOKEN de la organización
  → la máquina obtiene su token OIDC y asume MSRExternalBackendRole
  → el backend descubre el laboratorio por tags
  → estado READY en la UI, sin reset
  → si el laboratorio está parcheado: informa `reset_required` (sin resetear)
  → sólo un despliegue explícitamente autorizado ejecuta `app.lab_hook --confirm`
```

El usuario **no** ejecuta `aws login`, no aporta claves, no configura perfiles y no necesita
conocer el Instance ID actual. Lo único que hace falta una vez, y por organización, es:
`FLY_API_TOKEN` en los secretos de Devin, el proveedor OIDC y el rol en la cuenta AWS.

## 12. Decisiones abiertas antes de implementar

1. **Alojamiento**: ¿opción A (Fly.io con cuenta propia y `FLY_API_TOKEN` como secreto de
   organización) o se acepta la vista previa en la VM (opción C) para la demo?
2. **Slug de la organización de Fly**: es parte literal del emisor OIDC y de la trust policy;
   no me lo invento.
3. **Control de acceso a la URL pública**: la aplicación no tiene autenticación propia.
4. **Autorización para crear en AWS** el proveedor OIDC, `MSRExternalBackendRole` y la tabla
   de locks. Ojo: el descubrimiento de IAM mostró `iam:PutRolePolicy` e
   `iam:AttachRolePolicy` en *explicitDeny*, así que muy probablemente el rol y su política
   también deba crearlos el equipo corporativo de cloud, igual que en el diseño anterior.

Hasta que se cierren, ninguna mutación en AWS.
