"""
Motor de simulación del ciclo de remediación (6 fases) y del agente Devin.

ServiceNow = plano de control (estado, gates HITL). Devin = capa agente que en
cada fase produce artefactos (Impact Graph, MVT, resultados de test, IaC de lab,
PR, informe de auditoría). La ejecución técnica se delega a herramientas externas
(SCCM/BigFix/Ansible/CI-CD) que aquí se simulan.
"""
from __future__ import annotations
import random
from datetime import datetime, timedelta

from .seed import NOW, iso

PHASES = [
    ("detection", "Detección e ingesta"),
    ("prioritization", "Priorización"),
    ("pre_implementation", "Pre-implementación (MVT)"),
    ("lab_testing", "Pruebas en laboratorio"),
    ("prototype", "Validación en prototipo"),
    ("deployment", "Despliegue por anillos e informe"),
]
PHASE_IDS = [p[0] for p in PHASES]


# ---------------------------------------------------------------------------
# Carriles operativos (lanes) — flujo TO-BE y nivel de automatización
# ---------------------------------------------------------------------------
# Front común a los 3 carriles (antes del split por velocidad/riesgo).
SHARED_FLOW = [
    {"name": "Discovery & synchronization", "detail": "CMDB, inventario, fuentes de vulnerabilidad; detección de activos huérfanos.",
     "automation": "agentable", "mode": "Auto", "sla": "< 1 h"},
    {"name": "Triage y asignación de carril", "detail": "La Oficina de Riesgo y Exposición correlaciona KEV/EPSS, criticidad y exposición; traza la línea por activo y entidad.",
     "automation": "ai_assisted", "mode": "Auto", "sla": "< 30 min"},
]
# Flujo específico por carril (pasos, automatización y SLA), alineado con el modelo operativo.
LANE_FLOWS = {
    "critical": [
        {"name": "Emergency change pre-aprobado", "detail": "Pre-checks mínimos automatizados.", "automation": "agentable", "mode": "Auto", "sla": "< 30 min"},
        {"name": "Ejecución inmediata", "detail": "Fuera de ventana.", "automation": "agentable", "mode": "Auto", "sla": "< 1 h"},
        {"name": "Validación reforzada", "detail": "Batería ampliada de post-checks.", "automation": "ai_assisted", "mode": "Auto", "sla": "15-30 min"},
        {"name": "Escalado directo + RCA", "detail": "Cierre express con evidencia.", "automation": "ai_assisted", "mode": "Auto", "sla": "15-30 min"},
        {"name": "Resolución conjunta Cyber-IT", "detail": "Cierre basado en evidencia (vulns no resolubles por el flujo estándar).", "automation": "human", "mode": "Manual", "sla": "2-4 h"},
    ],
    "accelerated": [
        {"name": "Change estándar pre-aprobado", "detail": "Pre-checks y rollbacks automatizados.", "automation": "agentable", "mode": "Auto", "sla": "2-4 h"},
        {"name": "Primera ventana disponible", "detail": "Canary / rolling.", "automation": "agentable", "mode": "Auto", "sla": "0-24 h"},
        {"name": "Validación automática", "detail": "Por telemetría.", "automation": "ai_assisted", "mode": "Auto", "sla": "1-2 h"},
        {"name": "Retry / Rollback en la misma ventana", "detail": "Cierre con evidencia.", "automation": "agentable", "mode": "Auto", "sla": "2-4 h"},
    ],
    "standard": [
        {"name": "Ordinary change", "detail": "Mensual / trimestral.", "automation": "ai_assisted", "mode": "Semiauto", "sla": "1-3 días"},
        {"name": "Pre-validación completa", "detail": "Dependencias y rollback.", "automation": "human", "mode": "Manual", "sla": "1 día"},
        {"name": "Ejecución en ventana planificada", "detail": "Ventana de mantenimiento.", "automation": "human", "mode": "Manual", "sla": "Ventana"},
        {"name": "Validación funcional", "detail": "Pruebas funcionales.", "automation": "ai_assisted", "mode": "Semiauto", "sla": "1 día"},
        {"name": "Rollback closed-loop", "detail": "Cierre del bucle de rollback.", "automation": "human", "mode": "Manual", "sla": "1-2 h"},
        {"name": "Reporting y riesgo residual", "detail": "Informe y riesgo residual.", "automation": "human", "mode": "Manual", "sla": "< 30 min"},
    ],
}
# Nivel de automatización de cada una de las 6 fases del pipeline según el carril.
PHASE_AUTOMATION = {
    "critical":    ["agentable", "agentable", "agentable", "agentable", "ai_assisted", "ai_assisted"],
    "accelerated": ["agentable", "agentable", "agentable", "agentable", "ai_assisted", "ai_assisted"],
    "standard":    ["agentable", "ai_assisted", "ai_assisted", "ai_assisted", "human", "human"],
}


def lane_flow(lane):
    steps = LANE_FLOWS.get(lane, LANE_FLOWS["standard"])
    return {"shared": SHARED_FLOW, "steps": steps}


def phase_automation(lane, phase_index):
    levels = PHASE_AUTOMATION.get(lane, PHASE_AUTOMATION["standard"])
    return levels[phase_index] if 0 <= phase_index < len(levels) else "ai_assisted"


def _rng(task_id: str) -> random.Random:
    return random.Random(hash(task_id) & 0xFFFFFFFF)


# ---------------------------------------------------------------------------
# Impact Graph (blast radius)
# ---------------------------------------------------------------------------
def _build_adjacency(edges):
    """Índice de adyacencia bidireccional para BFS eficiente a escala (10k CIs)."""
    adj = {}
    for e in edges:
        adj.setdefault(e["source"], []).append((e["target"], e))
        adj.setdefault(e["target"], []).append((e["source"], e))
    return adj


def build_impact_graph(task, cis, edges, adj=None, max_nodes=60):
    ci_by_id = {c["id"]: c for c in cis}
    if adj is None:
        adj = _build_adjacency(edges)
    root_id = task["ci_id"]
    nodes = {}
    graph_edges = []

    def add(cid):
        if cid in ci_by_id and cid not in nodes:
            c = ci_by_id[cid]
            nodes[cid] = {
                "id": cid, "name": c["name"], "ci_class": c["ci_class"],
                "criticality": c.get("criticality", "medium"),
                "environment": c.get("environment", "-"),
                "is_root": cid == root_id,
            }

    add(root_id)
    # BFS over adjacency index in both directions (transitive impact), capped
    frontier = [root_id]
    seen = {root_id}
    depth = 0
    while frontier and depth < 4 and len(nodes) < max_nodes:
        nxt = []
        for cid in frontier:
            for neighbor, e in adj.get(cid, []):
                if neighbor in seen:
                    continue
                if len(nodes) >= max_nodes:
                    break
                add(cid); add(neighbor)
                graph_edges.append(e); seen.add(neighbor); nxt.append(neighbor)
        frontier = nxt
        depth += 1

    affected_layers = sorted({n["ci_class"] for n in nodes.values()})
    return {
        "nodes": list(nodes.values()),
        "edges": [{"source": e["source"], "target": e["target"], "type": e["type"]}
                  for e in graph_edges if e["source"] in nodes and e["target"] in nodes],
        "affected_layers": affected_layers,
        "affected_count": len(nodes),
        "business_services": [n["name"] for n in nodes.values() if n["ci_class"] == "business_service"],
    }


# ---------------------------------------------------------------------------
# MVT — Minimum Viable Test Plan (fase 3)
# ---------------------------------------------------------------------------
LAYER_TO_CLASSES = {
    "os": ["server"], "database": ["database"], "middleware": ["middleware"],
    "runtime": ["runtime"], "application": ["application"], "external": ["business_service"],
}


def build_mvt(task, impact, catalog):
    rng = _rng(task["id"] + "mvt")
    layers = set(impact["affected_layers"])
    exposed = task.get("exposed")
    track = task["track"]
    remediation_type = {"A": "patch", "B": "dependency", "C": "dependency"}.get(track, "patch")

    selected, excluded = [], []
    for tc in catalog:
        include = False
        reason = ""
        applies_layer = tc["layer"]
        # regla determinista: incluir si la capa está afectada
        layer_present = False
        if applies_layer == "os" and "server" in layers:
            layer_present = True
        elif applies_layer == "database" and "database" in layers:
            layer_present = True
        elif applies_layer == "middleware" and "middleware" in layers:
            layer_present = True
        elif applies_layer == "runtime" and "runtime" in layers:
            layer_present = True
        elif applies_layer == "application" and "application" in layers:
            layer_present = True
        elif applies_layer == "external" and exposed:
            layer_present = True

        # filtro por tipo de remediación
        type_ok = tc["remediation_type"] in ("any", remediation_type)
        # filtro por criticidad
        crit_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3, "any": 0}
        crit_ok = crit_rank.get(tc["criticality"], 0) <= crit_rank.get(task["criticality"], 1) or tc["criticality"] == "any"

        if layer_present and type_ok and crit_ok:
            include = True
            reason = f"Capa '{applies_layer}' presente en el blast radius y aplica a remediación '{remediation_type}'."
        elif layer_present and type_ok and not crit_ok:
            reason = f"Capa afectada pero criticidad de la prueba ({tc['criticality']}) superior a la del cambio; excluida para MVT."
        elif not layer_present:
            reason = f"Capa '{applies_layer}' no presente en el blast radius."
        else:
            reason = f"Tipo de remediación '{remediation_type}' no aplica a esta prueba."

        entry = {**tc, "reason": reason}
        (selected if include else excluded).append(entry)

    # Track B siempre añade SCA re-scan y regresión selectiva
    confidence = min(96, 60 + len(selected) * 3 + (10 if track == "B" else 6))
    return {
        "selected": selected,
        "excluded": excluded,
        "remediation_type": remediation_type,
        "confidence": confidence,
        "rationale": (
            f"Devin construyó el Impact Graph ({impact['affected_count']} CIs, capas: "
            f"{', '.join(impact['affected_layers'])}) y propuso el conjunto mínimo de "
            f"{len(selected)} pruebas que preserva la confianza del despliegue, excluyendo "
            f"{len(excluded)} pruebas no aplicables. Aprobación final: owner técnico / QA / SRE (HITL)."
        ),
    }


# ---------------------------------------------------------------------------
# Lab testing (fase 4)
# ---------------------------------------------------------------------------
def build_lab_results(task, mvt, force_pass=False):
    rng = _rng(task["id"] + "lab")
    results = []
    for tc in mvt["selected"]:
        # 92% pass; algún fallo ocasional en cambios de alta criticidad
        fail_chance = 0.0 if force_pass else (0.10 if task["criticality"] in ("critical", "high") else 0.04)
        status = "fail" if rng.random() < fail_chance else "pass"
        results.append({
            "test_id": tc["id"], "name": tc["name"], "layer": tc["layer"],
            "tool": tc["tool"], "status": status,
            "duration_s": rng.randint(4, 120),
            "evidence": f"{tc['evidence']}://evidence/{task['id']}/{tc['id']}",
        })
    passed = sum(1 for r in results if r["status"] == "pass")
    verdict = "pass" if passed == len(results) else "fail"
    return {
        "results": results, "passed": passed, "total": len(results),
        "verdict": verdict,
        "patch_tests": [r for r in results if r["layer"] in ("os", "database", "middleware", "runtime")],
        "app_tests": [r for r in results if r["layer"] in ("application", "external")],
    }


# ---------------------------------------------------------------------------
# Prototype (fase 5) — IaC lab blueprint
# ---------------------------------------------------------------------------
def build_prototype(task, impact):
    rng = _rng(task["id"] + "proto")
    components = []
    for layer in impact["affected_layers"]:
        if layer == "server":
            components.append({"type": "compute", "tool": "Terraform", "spec": "RHEL 8.8 / 4 vCPU / 16GB"})
        elif layer == "database":
            components.append({"type": "database", "tool": "Docker", "spec": "Oracle 19c (seed data)"})
        elif layer == "middleware":
            components.append({"type": "middleware", "tool": "Ansible", "spec": "Tomcat 9 / WebLogic"})
        elif layer == "runtime":
            components.append({"type": "runtime", "tool": "Ansible", "spec": "OpenJDK 17"})
        elif layer == "application":
            components.append({"type": "application", "tool": "Helm", "spec": f"{task['ci_name']} (staging build)"})
    approach = "ephemeral-iac" if task["track"] == "B" or rng.random() > 0.4 else "reuse-staging"
    verdict = "pass"
    return {
        "approach": approach,
        "lab_blueprint": components,
        "provision_tool": "Terraform + Ansible" if approach == "ephemeral-iac" else "Reused staging env",
        "metrics": {
            "cpu_peak_pct": rng.randint(35, 78),
            "mem_peak_pct": rng.randint(40, 82),
            "error_rate_pct": round(rng.uniform(0.0, 0.4), 2),
            "p95_latency_ms": rng.randint(120, 480),
        },
        "verdict": verdict,
        "teardown": "controlled-destroy" if approach == "ephemeral-iac" else "kept-for-analysis",
    }


# ---------------------------------------------------------------------------
# Deployment (fase 6) — rings + audit
# ---------------------------------------------------------------------------
RING_DEFS = [
    (0, "Anillo 0 · Interno / no crítico"),
    (1, "Anillo 1 · Producción bajo impacto"),
    (2, "Anillo 2 · Producción criticidad media"),
    (3, "Anillo 3 · Producción crítica"),
    (4, "Anillo 4 · Resto del alcance"),
]


def _deploy_executor(task, rng):
    return {
        "A": rng.choice(["Ansible", "BigFix", "SCCM", "Azure Update Manager"]),
        "B": "CI/CD (GitHub Actions)",
        "C": "GitOps (Argo CD + Helm) · Registry",
    }.get(task["track"], "CI/CD (GitHub Actions)")


def _prev_version(task, vi_version=None):
    v = task.get("vulnerable_version") or vi_version or "1.0.0"
    return v


def _fixed_version(version):
    """Deriva una versión 'parcheada' incrementando el patch."""
    parts = str(version).replace("v", "").split(".")
    try:
        parts = [int(p) for p in parts[:3]]
        while len(parts) < 3:
            parts.append(0)
        parts[-1] += 1
        return ".".join(str(p) for p in parts)
    except ValueError:
        return str(version) + "-patched"


def build_ring_actions(task, ring_no, assets, executor, ts_base):
    """Acciones concretas que ejecutan Devin + el ejecutor técnico para un anillo.

    Devuelve una lista ordenada de pasos con comando, actor, herramienta,
    salida simulada, estado y duración — para que la demo muestre que las
    acciones se ejecutaron realmente (no solo que 'se aprobó').
    """
    rng = _rng(task["id"] + f"actions{ring_no}")
    prev = _prev_version(task)
    fixed = _fixed_version(prev)
    comp = task.get("component", task["ci_name"])
    ci = task["ci_name"]
    steps = []

    def add(actor, tool, command, output, duration=None):
        steps.append({
            "seq": len(steps) + 1, "actor": actor, "tool": tool,
            "command": command, "output": output, "status": "ok",
            "duration_s": duration if duration is not None else rng.randint(2, 40),
        })

    if task["track"] == "C":
        add("Devin", "git", f"git checkout -b fix/{task['cve'].lower()}-image", f"Switched to branch 'fix/{task['cve'].lower()}-image'")
        add("Devin", "Docker", f"update base image: {comp} {prev} → {fixed}", "Dockerfile + manifests actualizados")
        add("GitHub Actions", "Docker", f"docker build --no-cache -t registry/{ci}:{fixed} .", f"Built image sha256:{rng.randint(10**11,10**12)}")
        add("Devin", "Trivy", f"trivy image registry/{ci}:{fixed}", "0 CRITICAL / 0 HIGH · imagen firmada (cosign)")
        add("Argo CD", "Helm", f"argocd app sync {ci} --revision {fixed} (canary {[5,10,25,35,100][min(ring_no,4)]}%)", f"Rollout progresivo a {assets} pods")
    elif task["track"] == "B":
        add("Devin", "git", f"git checkout -b fix/{task['cve'].lower()}-bump", f"Switched to branch 'fix/{task['cve'].lower()}-bump'")
        add("Devin", "CI/CD", f"bump {comp}: {prev} → {fixed}", f"1 file changed · lockfile updated")
        add("Devin", "CI/CD", f"gh pr merge --squash (ring {ring_no})", "Merged. Deploy workflow triggered.")
        add("GitHub Actions", "Docker", f"docker build -t {ci}:{fixed} .", f"Successfully tagged {ci}:{fixed}")
        add("GitHub Actions", "Helm", f"helm upgrade {ci} --set image.tag={fixed} --set canary.weight={[5,10,25,35,100][min(ring_no,4)]}", f"Rollout deployed to {assets} pods")
    else:
        add("Devin", executor, f"snapshot create {ci} --pre-patch (ring {ring_no})", f"Snapshot snap-{rng.randint(10000,99999)} created for {assets} hosts")
        add(executor, executor, f"deploy patch {comp} {prev} → {fixed} --limit ring{ring_no}", f"{assets} hosts targeted · maintenance window OK")
        add(executor, "OS", f"install {comp}-{fixed}", f"{assets}/{assets} hosts updated")
        add(executor, "OS", "systemctl restart affected-services", f"services restarted on {assets} hosts")

    # Post-checks (evidencia de validación tras aplicar)
    for chk in ["version-assert", "health-check", "smoke-test", "synthetic-probe"]:
        add("Devin", "post-check", chk, f"{chk}: OK ({assets}/{assets})", rng.randint(1, 12))
    return {"steps": steps, "from_version": prev, "to_version": fixed}


def build_rollback_plan(task, impact):
    """Plan de rollback armado desde el inicio (contemplación del rollback)."""
    rng = _rng(task["id"] + "rbplan")
    prev = _prev_version(task)
    fixed = _fixed_version(prev)
    ci = task["ci_name"]
    comp = task.get("component", ci)
    if task["track"] == "C":
        strategy = "GitOps rollback (revisión previa + imagen firmada)"
        steps = [
            {"actor": "Devin", "tool": "Argo CD", "command": f"argocd app rollback {ci} <previous-revision>",
             "desc": f"Sincroniza la revisión estable anterior (imagen {ci}:{prev})."},
            {"actor": "Argo CD", "tool": "Helm", "command": f"kubectl rollout undo deploy/{ci}",
             "desc": "Revierte el rollout al ReplicaSet sano; 100% del tráfico a la imagen previa."},
            {"actor": "Devin", "tool": "post-check", "command": "health-check + smoke-test",
             "desc": "Verifica salud de los pods tras el rollback."},
        ]
        snapshot_ref = f"registry/{ci}:{prev}"
    elif task["track"] == "B":
        strategy = "artifact-redeploy (imagen previa)"
        steps = [
            {"actor": "Devin", "tool": "Helm", "command": f"helm rollback {ci} <previous-revision>",
             "desc": f"Redeploy de la imagen {ci}:{prev} (revisión estable anterior)."},
            {"actor": "GitHub Actions", "tool": "CI/CD", "command": f"deploy {ci}:{prev} --canary.weight=100",
             "desc": "Restablece el 100% del tráfico al artefacto sano."},
            {"actor": "Devin", "tool": "post-check", "command": "health-check + smoke-test",
             "desc": "Verifica salud tras el rollback."},
        ]
        snapshot_ref = f"registry/{ci}:{prev}"
    else:
        strategy = "snapshot-restore (VM / paquete)"
        steps = [
            {"actor": "Devin", "tool": "Ansible", "command": f"package downgrade {comp} {fixed} → {prev}",
             "desc": f"Restaura la versión previa {comp}-{prev}."},
            {"actor": "Ansible", "tool": "IaC", "command": "restore snapshot <pre-patch>",
             "desc": "Restaura el snapshot tomado antes del parche si el downgrade no basta."},
            {"actor": "Ansible", "tool": "OS", "command": "systemctl restart affected-services",
             "desc": "Reinicia servicios y valida arranque."},
            {"actor": "Devin", "tool": "post-check", "command": "health-check + synthetic-probe",
             "desc": "Verifica salud tras el rollback."},
        ]
        snapshot_ref = f"snap-pre-{task['cve'].lower()}"
    return {
        "strategy": strategy,
        "snapshot_ref": snapshot_ref,
        "target_version": prev,
        "from_version": fixed,
        "rto_minutes": rng.choice([5, 8, 10, 15]),
        "auto_trigger": "fallo de post-checks / breach de health-check tras un anillo",
        "steps": steps,
        "tested_in_lab": True,
    }


def build_deployment(task, impact, progress_rings: int, rollback=None, rolled_back_rings=None):
    rng = _rng(task["id"] + "deploy")
    rolled_back_rings = set(rolled_back_rings or [])
    total_assets = max(6, impact["affected_count"] * rng.randint(2, 6))
    executor = _deploy_executor(task, rng)
    rings = []
    remaining = total_assets
    ts_base = 0
    for i, (rn, label) in enumerate(RING_DEFS):
        share = [0.05, 0.10, 0.25, 0.35, 0.25][i]
        assets = max(1, round(total_assets * share))
        if i == len(RING_DEFS) - 1:
            assets = max(1, remaining)
        remaining -= assets
        if rn in rolled_back_rings:
            status = "rolled_back"
        elif i < progress_rings:
            status = "completed"
        elif i == progress_rings:
            status = "in_progress"
        else:
            status = "pending"
        actions = build_ring_actions(task, rn, assets, executor, ts_base) if status in ("completed", "rolled_back") else None
        rings.append({
            "ring": rn, "label": label, "assets": assets, "status": status,
            "post_checks": ["version-assert", "health-check", "smoke-test", "synthetic-probe"] if status in ("completed", "rolled_back") else [],
            "result": {"completed": "healthy", "rolled_back": "reverted", "in_progress": "-", "pending": "-"}[status],
            "actions": actions,
            "health": {
                "error_rate_pct": round(rng.uniform(0.0, 0.3), 2),
                "p95_latency_ms": rng.randint(120, 420),
                "availability_pct": round(rng.uniform(99.9, 100.0), 2),
            } if status == "completed" else None,
        })
    exceptions = []
    if rng.random() > 0.5:
        exceptions.append({
            "asset": f"{task['ci_name']}-legacy-{rng.randint(1,9):02d}",
            "reason": rng.choice(["Sin ventana disponible", "Congelado por cambio", "Dependencia de proveedor", "Apagado"]),
            "owner": task["owner"], "expires": iso(NOW + timedelta(days=30)),
            "compensating_control": "WAF rule + network isolation",
        })
    pr_url = None
    if task["track"] in ("B", "C"):
        pr_url = f"https://github.com/{'bank-org'}/{task['ci_name']}/pull/{rng.randint(200,999)}"
    return {
        "executor": executor, "total_assets": total_assets, "rings": rings,
        "exceptions": exceptions, "pr_url": pr_url,
        "strategy": "risk-based progressive rings",
        "rollback_plan": build_rollback_plan(task, impact),
        "rollback": rollback or {"status": "armed", "triggered": False},
    }


def build_audit(task, impact, mvt, lab, proto, deploy):
    return {
        "report_id": f"AUD-{task['id'][-5:]}",
        "generated_at": iso(NOW),
        "trace": [
            {"step": "Finding", "ref": task["cve"], "detail": f"Detectado por escáneres, VI {task['vulnerable_item_id']}"},
            {"step": "Vulnerable Item", "ref": task["vulnerable_item_id"], "detail": f"Riesgo {task['risk_score']}/100, track {task['track']}"},
            {"step": "Impact Graph", "ref": f"{impact['affected_count']} CIs", "detail": ", ".join(impact["affected_layers"])},
            {"step": "Test Plan (MVT)", "ref": f"{len(mvt['selected'])} tests", "detail": f"Confianza {mvt['confidence']}%"},
            {"step": "Lab results", "ref": f"{lab['passed']}/{lab['total']}", "detail": f"Veredicto {lab['verdict']}"},
            {"step": "Prototype", "ref": proto["approach"], "detail": f"Veredicto {proto['verdict']}"},
            {"step": "Change Request", "ref": task["change_type"], "detail": "Aprobado (CAB)"},
            {"step": "Deployment", "ref": deploy["executor"], "detail": f"{deploy['total_assets']} activos en {len(deploy['rings'])} anillos"},
            {"step": "Rescan & closure", "ref": "verified", "detail": "Vulnerable Item → fixed"},
        ],
        "dora_relevant": any(n for n in impact["nodes"] if n["ci_class"] == "business_service"),
        "evidences_count": len(mvt["selected"]) + len(deploy["rings"]) + 3,
    }
