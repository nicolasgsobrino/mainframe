# Fase 2.8 — ECR, Application Load Balancer y lock distribuido en DynamoDB

Rama `devin/1785917443-msr-aws-phase1-1`, PR [#6](https://github.com/nicolasgsobrino/mainframe/pull/6).

**Cero llamadas a AWS y cero cambios en la cuenta**: sin `plan` real, `apply`, `destroy`,
`import`, `untaint` ni cambios de state; sin push a ECR, sin despliegue de ECS, sin
`StartAutomationExecution`, sin patch y sin reset. Todo lo verificado es local
(`terraform test` con `mock_provider "aws"`, tests estáticos y tests del lock con un doble
de DynamoDB).

## 1. Arquitectura

```text
usuario
  → Application Load Balancer (interno por defecto)
  → ECS Fargate :8080 (SPA compilada y /api en el mismo contenedor)
  → ECS Task Role (credenciales temporales del endpoint de metadatos)
  → AWS Systems Manager Automation
  → EC2 del laboratorio
```

```text
patch/reset desde la UI + reconciliación de release
  → lock distribuido en DynamoDB
  → exactamente una mutación del laboratorio a la vez
```

## 2. ECR (`infra/terraform/backend_ecr.tf`)

| Requisito | Implementación |
|---|---|
| repositorio privado dedicado | `aws_ecr_repository.backend`, `name = var.backend_ecr_repository_name` (`msr-poc-platform`); sin `aws_ecrpublic_*` ni `aws_ecr_repository_policy` |
| escaneo | `image_scanning_configuration { scan_on_push = true }` |
| cifrado | `encryption_configuration { encryption_type = "AES256" }` |
| lifecycle policy corta | `aws_ecr_lifecycle_policy.backend`: `imageCountMoreThan` `var.backend_ecr_retained_images` (5) → `expire` |
| tags no reescribibles | `image_tag_mutability = "IMMUTABLE"`, `force_delete = false` |
| output | `backend_ecr_repository_url` |
| desactivado por defecto | `enable_backend_ecr = false` (además del interruptor maestro `enable_real_resources`) |

Lifecycle policy exacta que se aplicaría:

```json
{"rules":[{"rulePriority":1,
           "description":"Conserva únicamente las 5 imágenes más recientes",
           "selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":5},
           "action":{"type":"expire"}}]}
```

### Publicación por OIDC (`.github/workflows/msr-platform-deploy.yml`)

`permissions: id-token: write` + `aws-actions/configure-aws-credentials@v4`
(`role-to-assume`) + `aws-actions/amazon-ecr-login@v2` → `docker build` → `docker push` →
`aws ecs register-task-definition` con la imagen recién publicada → `update-service` →
**una** sola ejecución del hook (`aws ecs run-task`). Sin `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `aws configure` ni `aws login`; la
`concurrency: msr-platform-deploy` se mantiene.

El paso de `register-task-definition` es nuevo: sin él el servicio seguiría arrancando la
imagen de la revisión anterior aunque el push hubiese tenido éxito.

## 3. ALB (`infra/terraform/backend_alb.tf`)

| Recurso | Configuración |
|---|---|
| `aws_lb.backend` | `internal = var.backend_alb_internal` (**`true` por defecto**), `application`, `drop_invalid_header_fields = true` |
| `aws_lb_target_group.backend` | `target_type = "ip"` (obligatorio con `awsvpc`), puerto 8080, health check `path = /api/health`, `matcher = 200`, 30 s / 5 s, 2 sanos / 3 fallidos |
| `aws_lb_listener.backend` | `var.backend_alb_port` (80) → `forward` al target group |
| `aws_ecs_service.backend` | bloque `load_balancer` dinámico (`container_name = backend`, `container_port = 8080`), `depends_on` del listener |

Reglas de security group:

| Regla | Origen/destino | Puerto |
|---|---|---|
| `aws_vpc_security_group_ingress_rule.backend_alb` | un recurso por CIDR de `backend_alb_ingress_cidrs`; **sin valor no se crea ninguna regla** | `backend_alb_port` |
| `aws_vpc_security_group_egress_rule.backend_alb_to_backend` | `referenced_security_group_id` = SG del backend | 8080 |
| `aws_vpc_security_group_ingress_rule.backend_from_alb` | `referenced_security_group_id` = SG del ALB (**nunca CIDR**) | 8080 |
| `backend_https` / `backend_dns_udp` (ya existentes) | APIs de AWS / resolver de la VPC | 443 / 53 |

Preconditions: al menos dos subnets (dos zonas) y bloqueo de la combinación
`backend_alb_internal = false` + `0.0.0.0/0`. Output: `backend_alb_dns_name` (vacío
mientras el ALB no exista) y `backend_alb_is_internal`. Sin CloudFront y sin túneles.

## 4. Lock distribuido

### Tabla (`infra/terraform/backend_locks.tf`)

`aws_dynamodb_table.lab_locks`: `name = msr-poc-lab-locks`, `hash_key = lab_id`
(atributo `S`), `PAY_PER_REQUEST`, `ttl { attribute_name = "expires_at", enabled = true }`,
`server_side_encryption`, `point_in_time_recovery`. Outputs: `backend_lock_table`
(nombre, ARN exacto, partition key, atributo TTL). Desactivada por defecto
(`enable_backend_lock_table = false`).

### Semántica (`backend/app/lab_locks.py`)

Ítem: `lab_id`, `owner` (correlation id), `holder` (host/pid, diagnóstico),
`operation` (`patch` | `reset` | `reconcile`), `reason`, `acquired_at`,
`expires_at` (epoch numérico, atributo TTL) y `expires_at_iso`.

```text
adquisición: PutItem condicional
  attribute_not_exists(lab_id) OR expires_at <= :now OR owner = :owner
liberación:  DeleteItem condicional
  owner = :owner
```

El TTL sólo limpia locks abandonados: la condición vuelve a comparar la caducidad, así que
la corrección **no depende del borrado asíncrono**. Un error inesperado de DynamoDB no
concede el lock (fail-closed). Backends: `sqlite` en `mock`/`aws-dry-run` (no hay mutación
en AWS) y `dynamodb` en ejecución real; `MSR_LAB_LOCK_BACKEND=auto` resuelve el que
corresponde y `MSR_LAB_LOCK_TABLE_NAME` pasa a ser obligatorio para una ejecución real.

Cobertura de las mutaciones:

| Operación | Punto de adquisición | Liberación |
|---|---|---|
| patch real | `Store.start_ring_patch_job` antes de crear el job | al estado terminal, en el fallo manejado y en el replay idempotente |
| reset real | `Store` antes de crear el job de restore | igual |
| reconciliación destructiva | `LabLifecycleManager.ensure_lab_ready` | `finally` |

La reconciliación puede reentrar en su propio lock al lanzar el reset (mismo `owner`) sin
soltarlo por el camino, y `GET /api/labs/{id}/reconciliation` publica `lock_backend` y el
estado del lock. La `concurrency` de GitHub Actions y el `RunTask` único del release siguen
siendo la serialización del release; el lock es un control de corrección adicional y
`desired_count = 1` no se usa como mecanismo de lock.

## 5. Política final del Task Role (añadido de esta fase)

```json
{
  "Sid": "SerializeLabMutationsWithTheLockTable",
  "Effect": "Allow",
  "Action": ["dynamodb:DeleteItem", "dynamodb:GetItem", "dynamodb:PutItem"],
  "Resource": "arn:aws:dynamodb:eu-north-1:133789123239:table/msr-poc-lab-locks"
}
```

`dynamodb:UpdateItem` **no** se concede: la renovación reescribe el ítem completo con
`PutItem` condicional, así que no se usa. Sin `dynamodb:*`, sin comodines de recurso, sin
acciones de administración de la tabla y sin índices (la tabla no tiene ninguno). El resto
de la política (Automation, SendCommand por tags, Auto Scaling) no cambia y sigue sin
`iam:PassRole` ni service role de Automation.

Ambos escenarios IAM siguen soportados: con `create_backend_task_role = true` Terraform
crea el rol con esta política; con `false` no se gestiona ningún recurso IAM y el documento
exacto que debe aplicar el equipo de cloud se publica en
`backend_task_role_permission_policy_json` (ya incluye el statement de DynamoDB) y
`backend_task_role_trust_policy_json`. Sin un ARN válido, el precondition de la task
definition detiene el despliegue.

## 6. Recursos que Terraform crearía

Laboratorio (sin cambios): **10** recursos.

| Bloque | Guarda | Recursos |
|---|---|---|
| ECR | `enable_backend_ecr` | `aws_ecr_repository.backend`, `aws_ecr_lifecycle_policy.backend` |
| ALB | `enable_backend_service` + `enable_backend_alb` | `aws_security_group.backend_alb`, `aws_vpc_security_group_ingress_rule.backend_alb` (uno por CIDR), `aws_vpc_security_group_egress_rule.backend_alb_to_backend`, `aws_vpc_security_group_ingress_rule.backend_from_alb`, `aws_lb.backend`, `aws_lb_target_group.backend`, `aws_lb_listener.backend` |
| Lock | `enable_backend_lock_table` | `aws_dynamodb_table.lab_locks` |

Todas las guardas valen `false` por defecto y dependen además de
`enable_real_resources`: con los valores predeterminados el plan sigue siendo
exactamente el del laboratorio. `output.backend_resource_summary` enumera lo que añadiría
cada bloque.

## 7. Supuestos de red pendientes

1. **Subnets del ALB.** `backend_alb_subnet_ids` está vacío: hacen falta dos subnets en
   zonas distintas (privadas si el ALB es interno) confirmadas por el equipo de red.
2. **Origen autorizado.** `backend_alb_ingress_cidrs` está vacío, así que el listener
   nacería sin ninguna entrada permitida hasta que se declare el rango corporativo.
3. **Alcance del ALB interno.** No está confirmado desde dónde se resolverá su DNS
   (VPN corporativa, peering o bastión).
4. **Salida de la task.** Sigue pendiente confirmar si las subnets del backend tienen NAT
   o si hacen falta endpoints de VPC; con el ALB se añade DynamoDB a la lista de endpoints
   necesarios (`ssm`, `ec2`, `autoscaling`, `dynamodb`, `ecr.api`, `ecr.dkr`, `logs`, S3).
5. **TLS.** El listener es HTTP: un ALB público exigiría certificado ACM y listener HTTPS,
   que no se añaden mientras la exposición sea interna.

## 8. Resultados

| Comprobación | Resultado |
|---|---|
| `pytest` (backend) | **365 passed** |
| `ruff check app tests` | limpio |
| `python -m compileall app tests` | sin errores |
| `npm run lint` / `npx tsc -b` / `npm run build` (frontend) | limpios |
| `terraform fmt -check -recursive` | limpio |
| `terraform validate` | `Success! The configuration is valid.` |
| `terraform test` | `Success! 27 passed, 0 failed.` |

Tests nuevos del lock (`backend/tests/test_lab_locks.py`): primera adquisición; segundo
proceso frente a un lock activo; reclamación segura de un lock caducado cuyo ítem sigue
presente; un no-owner no libera; reentrada del mismo owner; detalle del conflicto
(`LAB_OPERATION_LOCKED`); fail-closed ante un error inesperado de DynamoDB; selección de
backend por modo; tabla obligatoria en ejecución real; patch frente a reset; reset frente a
patch; task del servicio frente al hook de release; liberación tras éxito; liberación tras
fallo manejado; lock abandonado que vuelve a ser reclamable.

Tests nuevos de infraestructura (`tests/backend_exposure.tftest.hcl` y
`backend/tests/test_deployment_runtime.py`): nada nuevo se planifica con los valores
predeterminados; ECR privado, escaneado, cifrado, con tags inmutables y lifecycle policy;
URL del repositorio; ALB interno por defecto; target group `ip` en 8080; health check
`/api/health`; registro del servicio en el target group; ingress del backend sólo desde el
SG del ALB; listener cerrado sin orígenes declarados; rechazo de un ALB público abierto a
`0.0.0.0/0`; exigencia de dos zonas; clave, TTL, cifrado y recuperación de la tabla; ARN y
acciones de DynamoDB acotados a la tabla del lock; ausencia de `dynamodb:*`; workflow con
OIDC y sin credenciales estáticas; ASG del laboratorio intacto (1/1/1) y sin recursos
`aws_iam_*` del laboratorio.

## 9. Lo que sigue pendiente de autorización

Ninguna mutación se ha ejecutado. Antes de crear ECR, el ALB, la tabla de locks o de
publicar la imagen hacen falta: los datos de red del punto 7, la decisión sobre el
escenario IAM (A o B) y la autorización explícita del `apply`.
