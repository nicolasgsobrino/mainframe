# Fase 2.10 — ¿Puede MSR ejecutarse en el runtime de la propia sesión de Devin?

Informe de viabilidad con conclusión binaria. **Ninguna mutación en AWS**, ningún recurso
creado, ningún despliegue realizado y ninguna credencial permanente solicitada.

Este informe sustituye la opción A (Fly.io) de `ARCHITECTURE_REPORT_PHASE2_9.md` como camino
preferente. AWS sigue conteniendo **sólo** el laboratorio de parcheo.

---

## 0. Conclusión

> **A. EL RUNTIME DE LA SESIÓN DE DEVIN ES VIABLE.**

MSR (frontend + FastAPI) puede ejecutarse en la VM de la sesión y autenticarse contra AWS
**sin credenciales estáticas**: este despliegue enterprise emite tokens OIDC por sesión y
AWS puede confiar en su emisor mediante `sts:AssumeRoleWithWebIdentity`. El emisor está
verificado en vivo (§4).

Con una precisión que hay que aceptar explícitamente, porque no es lo que se pidió
literalmente («Devin expone la aplicación»):

> **No existe una URL pública ni un proxy de puertos.** La aplicación se consume a través de
> la pestaña **Desktop** de la sesión: el navegador corre dentro de la VM y el usuario lo
> controla en directo desde el webapp. El «preview» es, por tanto, la propia sesión —
> autenticada por Devin y limitada a quien tenga permisos de organización— no un enlace
> abierto a Internet.

Si el requisito real es un enlace que un tercero abra en su propio navegador sin entrar en el
webapp de Devin, **esa capacidad concreta no existe** y volvería a aplicar la opción A de la
fase 2.9. Todo lo demás del flujo pedido (sin instalación local, sin `aws login`, sin conocer
el Instance ID, sin `.env`) sí se cumple.

Las tres condiciones que faltan para ejecutarlo son autorizaciones, no capacidades:

1. crear en AWS el proveedor OIDC y `MSRExternalBackendRole` (§4.3);
2. aprobar el blueprint del repositorio con la acción `setup-aws-oidc` (§7);
3. crear la tabla de locks `msr-poc-lab-locks` (§6).

---

## 1. Cómo leer este informe

| Marca | Significado |
|---|---|
| **[VERIFICADO]** | Comprobado en esta VM/este despliegue enterprise, con el comando o la URL indicados |
| **[DOC]** | Documentación oficial de Devin, con enlace |
| **[INFERENCIA]** | Deducción razonada, no comprobada |
| **[ABIERTO]** | Decisión o dato que debe aportar una persona |

---

## 2. Ciclo de vida del runtime de la sesión

| Pregunta | Respuesta | Base |
|---|---|---|
| ¿Cuánto vive la VM? | Mientras la sesión no expire; **una sesión no puede continuarse más allá de 30 días** | **[DOC]** [Session Expiration](https://docs.devin.ai/admin/common-issues#session-expiration) |
| ¿Sobrevive a que Devin termine la tarea? | Sí: la sesión duerme por inactividad y despierta con un mensaje | **[DOC]** [Sleep and idle behavior](https://docs.devin.ai/admin/billing/usage#sleep-and-idle-behavior) |
| ¿Sobrevive a cerrar y reabrir la sesión? | Sí. El **disco** persiste entre suspensiones | **[VERIFICADO]** |
| ¿Sobreviven los procesos? | **No.** Al reanudar, la VM arranca de nuevo y los procesos lanzados a mano ya no existen | **[VERIFICADO]** |
| ¿Puede el frontend y FastAPI correr durante toda una demo? | Sí, mientras la sesión esté despierta | **[INFERENCIA]** de lo anterior |
| ¿Qué pasa al dormir/parar? | Se pierden los procesos, no los ficheros. Hay que relanzar el arranque (un comando, §7) | **[VERIFICADO]** |
| ¿Una sesión nueva hereda el estado? | No: arranca de un snapshot limpio con un clon fresco del repositorio | **[DOC]** [Blueprints](https://docs.devin.ai/onboard-devin/environment/blueprints) |

Evidencia de la persistencia del disco y de la pérdida de procesos, recogida en esta misma
sesión (creada el 2026-08-05):

```text
$ who -b                     → system boot  2026-08-07 19:08
$ uptime                     → up 12 min
$ stat .../backend/.venv     → 2026-08-05 06:25   (creado el primer día, sigue ahí)
$ stat ~/discovery.json      → 2026-08-07 17:40   (descubrimiento de red, sigue ahí)
$ ps -eo cmd | grep uvicorn  → (vacío)
$ curl localhost:8080/api/health → 000 (conexión rechazada)
```

El backend y el frontend que se levantaron para la demo anterior **ya no están corriendo**,
aunque el `.venv`, el repositorio y los ficheros generados sí siguen intactos. Consecuencia de
diseño: el arranque debe ser un comando idempotente y trivial de repetir, no un montaje
manual (§7).

---

## 3. Exposición de la aplicación

### 3.1 Lo que hay

| Pregunta | Respuesta | Base |
|---|---|---|
| ¿Se puede publicar el puerto 8080 en una URL de Devin? | **No hay mecanismo de exposición de puertos** en Devin Cloud: no existe herramienta de sesión que publique un puerto y la documentación de previews es de **Devin Desktop/Cascade**, donde el preview es local al equipo del usuario | **[DOC]** [In-IDE Preview](https://docs.devin.ai/desktop/previews#in-ide-preview) · **[VERIFICADO]** (ninguna herramienta de la sesión expone puertos) |
| ¿Es la VM alcanzable desde fuera? | No. Está tras NAT: `eth0 172.16.28.2/30`, salida por `100.23.34.160`, sin dirección de entrada y sin IMDS (`169.254.169.254` → sin respuesta) | **[VERIFICADO]** |
| ¿Cómo lo usa una persona entonces? | Pestaña **Desktop** de la sesión: ve y controla el navegador y el escritorio de la VM en directo | **[DOC]** [Interactive Browser](https://docs.devin.ai/work-with-devin/devin-session-tools#interactive-browser) · **[VERIFICADO]** en la demo anterior de esta sesión |
| ¿Está autenticado por Devin? | Sí: es el webapp enterprise, con login y permisos de organización (`ViewOrgSessions`, `ManageOrgSessions`) | **[DOC]** [Organization permissions](https://docs.devin.ai/api-reference/v3/overview#organization-permissions) |
| ¿Puede abrirlo otro usuario autorizado de la organización? | Sí, con esos permisos; la sesión se comparte por su enlace | **[DOC]** + **[VERIFICADO]**: dos usuarios distintos (`cfagundocruz`, `jmariscalalonso`) han intervenido en esta sesión |
| ¿Funcionan WebSocket/SSE/llamadas de API? | Sí, y sin riesgo de proxy: **el navegador corre dentro de la VM**, así que el tráfico de la SPA a `localhost:8080` no atraviesa ningún proxy de Devin. Lo que se transporta al usuario es la imagen del escritorio | **[INFERENCIA]** sólida a partir de la arquitectura verificada |
| ¿Es la URL estable? | Es la URL de la **sesión** (`.../sessions/<id>`): estable para esa sesión y no cambia al reiniciarse la VM, pero **cada sesión nueva tiene su propia URL** | **[VERIFICADO]** |

### 3.2 Lo que esto implica para la demo

```text
usuario autorizado del webapp enterprise
  → abre la sesión de Devin (login + permisos de organización)
  → pestaña Desktop
  → Chrome dentro de la VM en http://localhost:8080
  → FastAPI + SPA compilada
  → AWS (SSM Automation) → EC2 del laboratorio
```

Ventajas frente a un alojamiento externo: no hay superficie pública, el control de acceso es
el del propio Devin (SSO enterprise) y no hace falta cuenta de terceros. Limitaciones
honestas: un solo escritorio compartido (si dos personas miran la misma sesión, comparten el
mismo navegador), la experiencia es un escritorio remoto, y la sesión caduca a los 30 días.

---

## 4. Autenticación a AWS desde la VM de la sesión

### 4.1 Sí existe identidad de workload

**[DOC]** [Cloud Authentication with OIDC](https://docs.devin.ai/product-guides/oidc):
cada sesión recibe automáticamente un token de identidad de corta duración, firmado por
Devin y renovado durante la vida de la sesión, y hay una acción de blueprint específica para
AWS, [`setup-aws-oidc`](https://github.com/CognitionAI/actions/tree/main/setup-aws-oidc),
que instala un helper `credential_process` que intercambia ese token con
`AssumeRoleWithWebIdentity`. Literal de la documentación de la acción: *«avoiding static AWS
credentials»*.

**[VERIFICADO]** El emisor de este despliegue enterprise está publicado y activo:

```text
$ curl https://deloitte-es.devinenterprise.com/.well-known/openid-configuration
{
  "issuer": "https://deloitte-es.devinenterprise.com",
  "jwks_uri": "https://deloitte-es.devinenterprise.com/.well-known/jwks.json",
  "id_token_signing_alg_values_supported": ["RS256"],
  "grant_types_supported": ["urn:ietf:params:oauth:grant-type:token-exchange"],
  "claims_supported": ["iss","sub","aud","exp","iat","nbf","account_id","org_id",
                       "devin_id","build_job_id","devin_trigger",
                       "requesting_user_id","requesting_user_email","service_user_id"]
}

$ curl https://deloitte-es.devinenterprise.com/.well-known/jwks.json   → 200, clave RSA RS256
```

**[VERIFICADO]** Lo que hoy **no** está montado en esta sesión: el binario `devin-oidc` no
está instalado (`which devin-oidc` → vacío) porque el repositorio **no tiene blueprint**
(`read_environment_config` → *No blueprint found*). Es decir, la capacidad existe en la
plataforma pero no está habilitada para este repositorio: falta el paso de configuración
única del §7.

### 4.2 Parámetros del proveedor OIDC

| Parámetro | Valor | Base |
|---|---|---|
| URL del proveedor | `https://deloitte-es.devinenterprise.com` | **[VERIFICADO]** (`issuer`) |
| Audiencia (*client ID*) | `sts.amazonaws.com` | **[DOC]** valor por defecto de `audience` en `setup-aws-oidc` |
| Algoritmo / JWKS | RS256, `/.well-known/jwks.json` | **[VERIFICADO]** |
| Sujeto (`sub`) | Se compone de las claims elegidas en `subject-keys`; por defecto `org_id`, con el formato `org_id:<valor>` | **[DOC]** |
| Valor exacto del sujeto | **[ABIERTO]** — la documentación muestra `org_id:<uuid>` sin el prefijo `org-`, mientras que el identificador que ve la sesión es `org-4793cba689a54a11b8fe70ed031524c4`. Hay que confirmarlo con el administrador de Devin/soporte de Cognition (la propia documentación remite a ellos para el proveedor y el org ID) antes de escribir la condición del `sub` |

Claims disponibles para endurecer el sujeto: `account_id`, `org_id`, `devin_id`,
`devin_trigger`, `requesting_user_id`, `requesting_user_email`, `service_user_id`.

Recomendación: empezar por `subject-keys: "org_id"` (cualquier sesión de la organización que
use este blueprint puede operar el laboratorio, que es exactamente el objetivo de
repetibilidad) y, si se quiere restringir más, añadir `requesting_user_email` para limitarlo
a un grupo concreto de personas — a costa de romper el «cualquier usuario autorizado».

### 4.3 Trust policy de `MSRExternalBackendRole`

Plantilla exacta, con **un único valor pendiente de confirmar** (el del `sub`, §4.2):

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
          "deloitte-es.devinenterprise.com:sub": "org_id:<ORG_ID_CONFIRMADO>"
        }
      }
    }
  ]
}
```

Notas de seguridad:

- `aud` y `sub` con `StringEquals`, sin comodines: ninguna otra organización ni otro emisor
  puede asumir el rol.
- `duration-seconds` por defecto 3600; el helper renueva antes de expirar, así que **no hay
  nada que rotar ni revocar**. **[DOC]**
- Ninguna clave de acceso, ningún `SessionToken` copiado y ningún `aws login`.
- Auditoría: CloudTrail atribuye cada llamada a la sesión concreta a través del `sub`/la
  `RoleSessionName`. **[DOC]**

### 4.4 Política de permisos

La política de mínimo privilegio no cambia respecto a la fase 2.9: es exactamente la que
genera hoy Terraform en el output `backend_task_role_permission_policy_json`
(`infra/terraform/backend_iam.tf`), que cubre descubrimiento de EC2 por tags, validación de
cuenta/región/tags, estado de nodo gestionado de SSM, `StartAutomationExecution` y su
seguimiento, las operaciones de Auto Scaling necesarias para la recuperación, y el lock
acotado a `arn:aws:dynamodb:eu-north-1:133789123239:table/msr-poc-lab-locks`.

Sigue **sin** `iam:PassRole` (los runbooks no declaran `assumeRole`: la Automation corre con
la identidad que la inicia), sin `dynamodb:*`, sin `dynamodb:UpdateItem` y sin creación amplia
de infraestructura.

Un único cambio de nombre: el consumidor de esa política ya no es un Task Role de ECS, sino
`MSRExternalBackendRole`.

### 4.5 Configuración de la aplicación

```yaml
initialize:
  - uses: github.com/CognitionAI/actions/setup-aws-oidc@main
    with:
      role-arn: "arn:aws:iam::133789123239:role/MSRExternalBackendRole"
      region: "eu-north-1"
```

La acción escribe un `credential_process` en el perfil `default` de `~/.aws/config`, así que
boto3 obtiene credenciales temporales por la cadena estándar y la configuración de MSR se
queda **vacía**, como se exigió:

```env
MSR_PATCH_PROVIDER=aws-automation
MSR_RESTORE_PROVIDER=aws-automation
MSR_DRY_RUN=true
MSR_LAB_RECONCILE_ON_STARTUP=false
MSR_AWS_PROFILE=
MSR_AWS_ROLE_ARN=
MSR_AWS_REGION=eu-north-1
```

`credentials_source()` seguirá informando `default-chain`, que es lo correcto: la federación
es la cadena de credenciales del runtime, no un assume-role de la aplicación.

### 4.6 Fallback (sólo si no se autoriza el proveedor OIDC)

No se propone como arquitectura, sólo por completitud, y **no se ha creado nada**:

- secreto de **organización** en Devin (llega como variable de entorno a toda sesión
  autorizada, §5) con una credencial de un usuario IAM dedicado;
- misma política de mínimo privilegio del §4.4, nunca la credencial de administrador
  (la que se usó en el descubrimiento era `AWS_133789123239_Admin` y ya caducó);
- **limitación de seguridad explícita**: una clave de usuario IAM es de **larga duración**;
  no hay forma realista de refrescarla automáticamente sin federación, así que quedaría
  expuesta al robo mientras exista, con rotación manual (p. ej. 90 días) y radio de impacto
  igual a la política del §4.4 (operar el laboratorio, nunca crear infraestructura);
- eliminación: borrar el secreto de organización y desactivar/eliminar la clave en IAM.

Con la federación disponible y verificada, este camino no debería usarse.

---

## 5. Secretos de organización

**[DOC]** [Blueprint reference — Secrets](https://docs.devin.ai/onboard-devin/environment/blueprint-reference#secrets):
los secretos configurados en el UI se inyectan como variables de entorno, se reinyectan al
inicio de **cada** sesión y se eliminan de la imagen del snapshot. Ámbitos:

| Ámbito | Comportamiento |
|---|---|
| Enterprise | Disponible en todas las organizaciones de la enterprise |
| **Organización** | Variable de entorno en todos los pasos y sesiones de la organización (el secreto de organización gana ante una colisión de nombre con el de enterprise) |
| **Repositorio** | Fichero por repositorio en `/run/repo_secrets/{owner/repo}/.env.secrets`, cargado al trabajar en ese repositorio |
| Sesión / personal | **No** visibles en los builds de snapshot |

**[VERIFICADO]** en esta VM: los secretos de organización llegan efectivamente como variables
de entorno (`GITHUB_TOKEN`, `SNYK_TOKEN`, `JIRA_API_TOKEN`, `MY_BQ_TOKEN`… presentes en el
entorno). Y las credenciales de este ejercicio están en ámbito **sesión**
(`secret:session:AWS_MSR_READONLY_*`), por lo que **no** servirán en sesiones futuras ni en
los builds — de ahí que la configuración de una vez tenga que ser de organización o de
repositorio.

Conclusión para el objetivo pedido: sí existe el modelo «configuración única →
cualquier sesión autorizada recibe lo necesario». Y con OIDC, además, **el secreto que hay que
guardar es ninguno**: sólo el ARN del rol, que no es sensible y va en el blueprint.

---

## 6. Persistencia

AWS sigue siendo la fuente de verdad del laboratorio: EC2 actual, estado vulnerable/parcheado,
kernel, estado de SSM y ejecuciones de patch/reset.

Lo que la aplicación guarda hoy en SQLite (`data/msr_jobs.db`): jobs de parcheo/restauración y
sus eventos, el registro del `LabTarget` y el lock local heredado. El resto del plano de
control es estado en memoria generado por `app/seed.py`, determinista.

| Estado | ¿Necesita volumen? | Por qué |
|---|---|---|
| Datos de la demo (tareas, CMDB, KPIs) | No | Determinista desde `seed` en cada arranque |
| Registro del `LabTarget` | No | Reconstruible: valores por defecto del laboratorio + descubrimiento por tags |
| Estado del laboratorio | No | Se lee de AWS (tags, AMI, advisory, SSM, ASG) |
| Historial de jobs | No para la demo | Es trazabilidad de una sesión; la verdad operativa está en las ejecuciones de SSM Automation, consultables en AWS |
| Jobs en vuelo | No | Se rehidratan por polling contra la ejecución remota mientras la sesión viva; una sesión nueva no hereda jobs porque tampoco hereda demo |

**Decisión: no se introduce ningún volumen persistente** (ni Fly Volume ni Postgres). El
fichero SQLite vive en el disco de la sesión, que **sí** persiste entre suspensiones
(§2), y una sesión nueva lo reconstruye desde AWS + semilla determinista. Esto es
exactamente el rediseño «estado desechable» que se pidió, y hay que asumir su consecuencia:
el historial de jobs es por sesión.

---

## 7. Flujo repetible «arranca la PoC de MSR»

Hoy **no hay blueprint** para `nicolasgsobrino/mainframe` (**[VERIFICADO]**), así que el
montaje sigue siendo manual. La configuración de una vez que hace repetible el flujo:

```yaml
# blueprint del repositorio (propuesta; requiere aprobación del usuario y reconstruir snapshot)
initialize:
  - uses: github.com/CognitionAI/actions/setup-aws-oidc@main
    with:
      role-arn: "arn:aws:iam::133789123239:role/MSRExternalBackendRole"
      region: "eu-north-1"
maintenance: |
  (cd msr-platform/backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt)
  (cd msr-platform/frontend && npm install)
knowledge:
  - name: startup
    contents: |
      msr-platform/scripts/build.sh
      (cd msr-platform/backend && .venv/bin/uvicorn app.main:app --port 8080)
```

Y el flujo objetivo, ya sin AWS del lado de la aplicación:

```text
usuario autorizado
  → abre Devin y pide «arranca la PoC de MSR»
  → la sesión ya trae dependencias y perfil AWS federado (blueprint)
  → un comando compila la SPA y levanta FastAPI en :8080
  → el backend valida cuenta/región/tags (fail-closed) y descubre la EC2 por tags
  → un único `python -m app.lab_hook` comprueba/reconcilia el laboratorio
     (destructivo sólo con `--confirm` explícitamente autorizado)
  → Devin abre la aplicación en el navegador de la VM
  → el usuario opera desde la pestaña Desktop
```

El usuario no necesita conocer el Instance ID, la cuenta, la CLI de AWS, los valores del
`.env` ni los runbooks; tampoco instala nada en su equipo ni ejecuta `aws login`.

Pendiente de implementación (fase siguiente, si se aprueba): un script de arranque
idempotente en `msr-platform/scripts/` que encapsule compilación, arranque y comprobación de
salud, el blueprint anterior y un playbook que lo invoque.

---

## 8. Lock distribuido

Se **mantiene** el lock en DynamoDB, y la razón es más fuerte que con ECS: cada sesión de
Devin es una VM con disco propio (**[VERIFICADO]**), y dos personas pueden abrir dos sesiones
que apunten al **mismo** laboratorio de AWS. Un lock en SQLite es local a una VM y no serializa
nada entre sesiones.

- Tabla: `msr-poc-lab-locks`, clave de partición `lab_id`, TTL en `expires_at`.
- Cubre patch real, reset real y reconciliación destructiva.
- Permisos exactos, ya implementados y sin cambios:

```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"],
  "Resource": "arn:aws:dynamodb:eu-north-1:133789123239:table/msr-poc-lab-locks"
}
```

`dynamodb:UpdateItem` sigue fuera: la adquisición y la renovación son `PutItem` condicional y
el release es `DeleteItem` condicional por owner.

---

## 9. Qué queda en AWS

| Recurso | Estado |
|---|---|
| EC2 + ASG del laboratorio, Launch Template/AMI, security group | Existente |
| Integración de nodo gestionado de SSM | Existente |
| `MSR-PatchLinuxInstance`, `MSR-ResetLabInstance` | Gestionados por este Terraform |
| Tabla `msr-poc-lab-locks` | Por crear (pendiente de autorización) |
| Proveedor OIDC `deloitte-es.devinenterprise.com` + `MSRExternalBackendRole` | Por crear (pendiente de autorización) |
| ECS/Fargate, ECR, ALB, redes de aplicación, Lambda, EKS | **No objetivo** — marcados superseded en la fase 2.9 |

Fly.io queda como opción A de reserva: sólo tendría sentido si se exige una URL pública
utilizable fuera del webapp de Devin (§3.1). No se ha creado ninguna cuenta ni se ha pedido el
slug de ninguna organización de Fly.

---

## 10. Autorizaciones pendientes

1. Aceptar que el «preview» es la pestaña Desktop de la sesión y no una URL pública.
2. Confirmar con el administrador de Devin/Cognition el valor exacto del `sub`
   (`org_id:<...>`) y el proveedor OIDC del despliegue.
3. Autorizar en AWS la creación del proveedor OIDC, `MSRExternalBackendRole` con la trust
   policy del §4.3 y la política del §4.4, y la tabla de locks. Recordatorio del descubrimiento
   de la fase 2.7: la cuenta deniega `iam:AttachRolePolicy`/`iam:PutRolePolicy`, así que el rol
   lo debe crear el equipo de cloud, no este Terraform.
4. Aprobar el blueprint del repositorio (§7) para que la federación y las dependencias estén
   en cualquier sesión futura.
5. Después de eso, y sólo entonces, autorizar la validación real (`MSR_DRY_RUN=false`, patch y
   reset).

Nada de lo anterior se ha ejecutado: cero mutaciones en AWS, cero recursos creados, cero
credenciales permanentes solicitadas.
