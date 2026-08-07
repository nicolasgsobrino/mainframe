# Playbook — «arranca la PoC de MSR»

Para Devin: cuando un usuario autorizado pida arrancar, levantar o demostrar la PoC de MSR en
esta sesión, sigue exactamente estos pasos. No hace falta preguntarle nada al usuario: ni
credenciales, ni Instance ID, ni valores de configuración.

## Pasos

1. Ejecuta el arranque idempotente:

   ```bash
   msr-platform/scripts/start_poc.sh
   ```

   Es repetible: si la sesión se durmió y los procesos murieron, vuelve a ejecutarlo tal cual.
   `MSR_POC_MODE=mock` fuerza la demo simulada y `MSR_POC_MODE=aws` exige identidad de AWS
   (falla si no la hay, en vez de degradar a mock silenciosamente).

2. Comprueba la salida del propio script:
   - identidad de AWS (`sts:GetCallerIdentity`) y providers elegidos;
   - `/api/health` respondiendo en `:8080`;
   - resultado de la comprobación **no destructiva** del laboratorio.

3. Abre `http://localhost:8080` en el navegador de la VM y deja al usuario operar desde la
   pestaña **Desktop** de la sesión (es la superficie oficial de la demo: no hay URL pública).

4. Informa al usuario en una sola frase: modo de ejecución (`mock`, `aws-dry-run` o
   `aws-real`), estado del laboratorio y que ya puede operar desde Desktop.

## Reglas

- **Nunca** ejecutes un patch ni un reset reales por iniciativa propia. `MSR_DRY_RUN=true` es el
  valor por defecto y no se cambia sin que el usuario lo pida explícitamente.
- **Nunca** ejecutes `python -m app.lab_hook --confirm` (reset destructivo: recrea la EC2) sin
  autorización explícita en ese mensaje.
- **Nunca** pidas claves de AWS, un perfil o `aws login`: la identidad la aporta la federación
  OIDC de la sesión. Si no hay identidad, arranca en `mock` y dilo.
- **Nunca** fijes un Instance ID: el objetivo se resuelve por tags y cada reset lo cambia.
- Si el laboratorio no está listo, informa del `error_code` que devuelve el hook y para; no
  intentes repararlo mutando AWS.

## Contexto

Arquitectura, bootstrap único de AWS y detalle del arranque:
`msr-platform/ARCHITECTURE_REPORT_PHASE2_11.md`.
