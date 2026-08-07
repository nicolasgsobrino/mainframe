#!/usr/bin/env bash
# Hook de reconciliación de una sola ejecución por release.
#
# Lanza UNA task de ECS con la misma imagen del servicio y el comando sustituido
# por `python -m app.lab_hook`, espera a que termine y propaga su código de
# salida. El servicio nunca reconcilia en el arranque de sus réplicas
# (MSR_LAB_RECONCILE_ON_STARTUP=false) y el lock durable de SQLite impide que dos
# invocaciones simultáneas reseteen el mismo laboratorio.
#
#   ./release_lab_hook.sh                 # informa; si el lab ya es vulnerable, action=none
#   ./release_lab_hook.sh --confirm       # SOLO para un release autorizado a restaurar
#
# Las credenciales las aporta el rol del pipeline (OIDC) y la task usa su Task
# Role: este script no acepta ni exporta claves estáticas.
set -euo pipefail

CLUSTER="${MSR_ECS_CLUSTER:?define MSR_ECS_CLUSTER}"
TASK_DEFINITION="${MSR_ECS_TASK_DEFINITION:?define MSR_ECS_TASK_DEFINITION}"
SUBNETS="${MSR_ECS_SUBNETS:?define MSR_ECS_SUBNETS (lista separada por comas)}"
SECURITY_GROUPS="${MSR_ECS_SECURITY_GROUPS:?define MSR_ECS_SECURITY_GROUPS}"
REGION="${MSR_AWS_REGION:-eu-north-1}"
CONTAINER="${MSR_ECS_CONTAINER_NAME:-backend}"

COMMAND='["python","-m","app.lab_hook"]'
if [[ "${1:-}" == "--confirm" ]]; then
  # Restauración autorizada: sólo con esta bandera el hook puede resetear.
  COMMAND='["python","-m","app.lab_hook","--confirm"]'
elif [[ -n "${1:-}" ]]; then
  echo "Uso: $0 [--confirm]" >&2
  exit 2
fi

echo "Lanzando el hook de reconciliación en ${CLUSTER} (${REGION}): ${COMMAND}"
task_arn="$(aws ecs run-task \
  --region "${REGION}" \
  --cluster "${CLUSTER}" \
  --task-definition "${TASK_DEFINITION}" \
  --launch-type FARGATE \
  --count 1 \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SECURITY_GROUPS}],assignPublicIp=DISABLED}" \
  --overrides "{\"containerOverrides\":[{\"name\":\"${CONTAINER}\",\"command\":${COMMAND}}]}" \
  --started-by "msr-release-hook" \
  --query 'tasks[0].taskArn' --output text)"

echo "Task: ${task_arn}"
aws ecs wait tasks-stopped --region "${REGION}" --cluster "${CLUSTER}" --tasks "${task_arn}"

exit_code="$(aws ecs describe-tasks --region "${REGION}" --cluster "${CLUSTER}" \
  --tasks "${task_arn}" \
  --query "tasks[0].containers[?name=='${CONTAINER}'].exitCode | [0]" --output text)"

echo "Código de salida del hook: ${exit_code}"
# 0 = laboratorio listo (vulnerable y sano). Cualquier otro valor detiene el release.
[[ "${exit_code}" == "0" ]]
