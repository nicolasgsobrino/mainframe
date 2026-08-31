"""
Motor de simulación del ciclo de remediación (6 fases) y del agente Devin.

ServiceNow = plano de control (estado, gates HITL). Devin = capa agente que en
cada fase produce artefactos (Impact Graph, MVT, resultados de test, IaC de lab,
PR, informe de auditoría). La ejecución técnica se delega a herramientas externas
(SCCM/BigFix/Ansible/CI-CD) que aquí se simulan.
"""
from __future__ import annotations
import math
import random
from datetime import timedelta

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


# Perfil de remediación: determina si la mitigación provoca caída del activo y,
# por tanto, si el blast radius se propaga a los sistemas dependientes. Una
# actualización de dependencia se despliega en rolling y el servicio no cae, de
# modo que el impacto queda acotado al propio activo aunque otros dependan de él.
REMEDIATION_PROFILES = {
    "patch": {
        "restart_scope": "instance",
        "downtime_required": True,
        "rationale": ("El parche de sistema operativo exige reiniciar la instancia: "
                      "los sistemas dependientes sí sufren la ventana de indisponibilidad."),
    },
    "dependency": {
        "restart_scope": "service",
        "downtime_required": False,
        "rationale": ("La actualización de la dependencia se despliega en rolling sin "
                      "caída del servicio: los dependientes no se ven afectados."),
    },
}


def remediation_profile(task):
    """Tipo de remediación previsto y si implica caída (mismo criterio que el MVT)."""
    rtype = {"A": "patch", "B": "dependency", "C": "dependency"}.get(task["track"], "patch")
    return {"remediation_type": rtype, **REMEDIATION_PROFILES[rtype]}


def build_impact_graph(task, cis, edges, adj=None, max_nodes=10):
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
                # Identidad del objetivo para providers reales (opcional).
                "logical_target_id": c.get("logical_target_id", cid),
                "instance_id": c.get("instance_id"),
                "account_id": c.get("account_id"),
                "region": c.get("region"),
                "tags": c.get("tags") or {},
                "ssm_managed": bool(c.get("ssm_managed")),
                "os": c.get("os"),
            }

    add(root_id)
    # BFS over adjacency index in both directions (transitive impact), capped
    frontier = [root_id]
    seen = {root_id}
    depth = 0
    while frontier and depth < 3 and len(nodes) < max_nodes:
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
    profile = remediation_profile(task)
    propagates = profile["downtime_required"]
    return {
        "nodes": list(nodes.values()),
        "edges": [{"source": e["source"], "target": e["target"], "type": e["type"]}
                  for e in graph_edges if e["source"] in nodes and e["target"] in nodes],
        "affected_layers": affected_layers,
        "affected_count": len(nodes),
        "business_services": [n["name"] for n in nodes.values() if n["ci_class"] == "business_service"],
        # El alcance del blast radius depende de la mitigación: sin caída del
        # activo, el impacto no se propaga a quienes dependen de él.
        "remediation_type": profile["remediation_type"],
        "downtime_required": propagates,
        "restart_scope": profile["restart_scope"],
        "blast_scope": "propagated" if propagates else "local",
        "impacted_count": len(nodes) if propagates else 1,
        "blast_rationale": profile["rationale"],
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
    remediation_type = remediation_profile(task)["remediation_type"]

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
# Deployment (fase 6) — anillos por ENTORNO (realidad del cliente) + audit
# ---------------------------------------------------------------------------
# Los anillos ya NO se definen por criticidad, sino por la realidad del cliente:
# el mismo alcance de CIs impactados progresa por entornos. En Laboratorio y
# Pre-productivo se levanta una RÉPLICA de la infraestructura impactada y se
# ejecuta toda la batería de pruebas; en Canary y Producción el despliegue es
# progresivo (subconjunto → controlado → total) sobre los activos reales.
RING_DEFS = [
    (1, "Anillo 1 · Laboratorio"),
    (2, "Anillo 2 · Canary"),
    (3, "Anillo 3 · Pre-productivo"),
    (4, "Anillo 4 · Productivo controlado"),
    (5, "Anillo 5 · Productivo total"),
]

# Definición de cada etapa: entorno, si es réplica o activos reales, alcance
# (porcentaje del blast radius), si ejecuta pruebas, y ventana.
RING_STAGES = {
    1: {"key": "lab", "env": "Laboratorio", "kind": "replica", "pct": 100, "tests": True, "prod": False,
        "scope": "all", "window": "Inmediata · entorno aislado sin impacto en negocio",
        "purpose": "Réplica efímera (IaC) de toda la infraestructura impactada; se aplica el fix y se ejecuta la batería completa de pruebas."},
    2: {"key": "canary", "env": "Canary", "kind": "real", "pct": 10, "tests": False, "prod": True,
        "scope": "canary", "window": "Ventana estándar · vigilancia reforzada",
        "purpose": "Despliegue a un subconjunto mínimo de activos reales para observar el comportamiento con tráfico real."},
    3: {"key": "preprod", "env": "Pre-productivo", "kind": "replica", "pct": 100, "tests": True, "prod": False,
        "scope": "all", "window": "Ventana de pre-producción",
        "purpose": "Despliegue en pre-producción; pruebas funcionales y de integración con datos representativos."},
    4: {"key": "prod_controlled", "env": "Productivo controlado", "kind": "real", "pct": 50, "tests": False, "prod": True,
        "scope": "half", "window": "Ventana de mantenimiento acordada",
        "purpose": "Despliegue controlado a una parte de producción, vigilando la telemetría antes de generalizar."},
    5: {"key": "prod_full", "env": "Productivo total", "kind": "real", "pct": 100, "tests": False, "prod": True,
        "scope": "all_real", "window": "Ventana planificada final",
        "purpose": "Despliegue al 100% del alcance productivo; verificación y cierre del despliegue."},
}
CANARY_PCT = [100, 10, 100, 50, 100]

# Orden de despliegue por dependencia: de la infraestructura (dependencia) hacia
# el servicio de negocio (dependiente). A igualdad, de menor a mayor criticidad.
CLASS_ORDER = {
    "network_device": 0, "cloud_resource": 1, "server": 2, "database": 3,
    "runtime": 4, "middleware": 4, "container": 5, "application": 6, "business_service": 7,
}
CRIT_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def order_by_dependency(impact):
    """Ordena los CIs impactados de dependencia a dependiente (infra → app →
    servicio de negocio); a igualdad, de menor a mayor criticidad (canary seguro)."""
    nodes = list(impact["nodes"])
    nodes.sort(key=lambda n: (CLASS_ORDER.get(n["ci_class"], 5),
                              CRIT_ORDER.get(n.get("criticality", "medium"), 1),
                              n["id"]))
    return nodes


def _scope_nodes(ordered, scope):
    n = len(ordered)
    if scope == "canary":
        return ordered[:max(1, math.ceil(n * 0.10))]
    if scope == "half":
        return ordered[:max(1, math.ceil(n * 0.50))]
    return list(ordered)  # "all" (réplica) / "all_real"


def assign_impact_to_rings(impact):
    """Cada anillo recibe su alcance de CIs impactados (ordenados por dependencia).
    Lab/Pre-productivo = réplica del 100%; Canary/Prod = despliegue progresivo real."""
    ordered = order_by_dependency(impact)
    return {rn: _scope_nodes(ordered, RING_STAGES[rn]["scope"]) for rn, _ in RING_DEFS}


def _asset_reason(stage: dict, ci_class: str, crit: str, is_root: bool) -> str:
    what = "réplica del activo" if stage["kind"] == "replica" else "activo real"
    if is_root:
        return (f"CI raíz de la vulnerabilidad ({ci_class}, {crit}); {what} en «{stage['env']}». "
                f"Se despliega en primer lugar por ser origen del blast radius.")
    return (f"CI impactado ({ci_class}, {crit}) dentro del blast radius; {what} en «{stage['env']}» "
            f"(orden por dependencia: infraestructura → aplicación → servicio).")


def build_ring_plan(task, impact, ring_no, label, canary_pct, executor, ring_nodes,
                    exclusions=None, preapproval=None):
    """Informe pre-anillo por ETAPA/entorno: los CIs impactados de esta etapa
    (réplica o reales), sus dependencias (subgrafo del Impact Graph), criterios de
    entrada, ventana y estado de pre-aprobación (auditoría Human-Driven)."""
    rng = _rng(task["id"] + f"plan{ring_no}")
    stage = RING_STAGES[ring_no]
    is_replica = stage["kind"] == "replica"
    excluded = set(exclusions or [])
    node_by_id = {n["id"]: n for n in impact["nodes"]}
    ring_ids = {n["id"] for n in ring_nodes}

    # Activos de este anillo, ordenados por dependencia (infra → servicio).
    assets = []
    for n in ring_nodes:
        is_root = bool(n.get("is_root"))
        display = f"réplica · {n['name']}" if is_replica else n["name"]
        assets.append({
            "id": n["id"], "name": display, "ci_class": n["ci_class"],
            "criticality": n.get("criticality", "medium"),
            "environment": stage["env"],
            "is_root": is_root,
            "logical_target_id": n.get("logical_target_id", n["id"]),
            "instance_id": n.get("instance_id"),
            "account_id": n.get("account_id"),
            "region": n.get("region"),
            "tags": n.get("tags") or {},
            "ssm_managed": bool(n.get("ssm_managed")),
            "reason": _asset_reason(stage, n["ci_class"], n.get("criticality", "medium"), is_root),
            "excluded": n["id"] in excluded,
        })

    # Dependencias = vecinos (de los CIs impactados) según relaciones del Impact Graph.
    deps = {}
    for e in impact["edges"]:
        s, t = e["source"], e["target"]
        for a, b in ((s, t), (t, s)):
            if a in ring_ids and b in node_by_id and b not in ring_ids and b not in deps:
                nb = node_by_id[b]
                deps[b] = {
                    "id": b, "name": nb["name"], "ci_class": nb["ci_class"],
                    "criticality": nb.get("criticality", "medium"),
                    "relation": e["type"], "of": node_by_id[a]["name"],
                }
    dependencies = list(deps.values())

    # Subgrafo del anillo: CIs impactados + sus dependencias directas.
    graph_ids = ring_ids | set(deps.keys())
    graph_nodes = [dict(node_by_id[i]) for i in graph_ids if i in node_by_id]
    graph_edges = [e for e in impact["edges"] if e["source"] in graph_ids and e["target"] in graph_ids]

    assets_count = len(assets)
    selected_n = assets_count - len([a for a in assets if a["excluded"]])

    entry_criteria = [
        {"check": "MVT aprobado (HITL)", "ok": True},
        {"check": "Prototipo validado", "ok": True},
        {"check": "Change Request autorizado (ITSM)", "ok": True},
        {"check": "Ventana disponible", "ok": True},
        {"check": "Plan de rollback probado en lab", "ok": True},
        {"check": "Sin conflictos de cambio abiertos", "ok": bool(rng.random() > 0.15)},
    ]
    if is_replica:
        scope_txt = (f"réplica del 100% del alcance ({assets_count} CIs) donde se aplica el fix "
                     f"y se ejecuta toda la batería de pruebas")
    elif stage["scope"] == "canary":
        scope_txt = f"subconjunto canary del {stage['pct']}% ({assets_count} CIs reales) para observar tráfico real"
    elif stage["scope"] == "half":
        scope_txt = f"despliegue controlado al {stage['pct']}% de producción ({assets_count} CIs reales)"
    else:
        scope_txt = f"despliegue al 100% del alcance productivo ({assets_count} CIs reales)"

    rationale = (
        f"{stage['purpose']} En esta etapa el alcance es un {scope_txt}, ordenados por dependencia "
        f"(infraestructura → aplicación → servicio de negocio) con {len(dependencies)} dependencias directas. "
        f"Ejecutor: {executor}."
    )
    return {
        "ring": ring_no,
        "label": label,
        "band": stage["env"],
        "environment": stage["env"],
        "kind": stage["kind"],
        "is_replica": is_replica,
        "runs_tests": stage["tests"],
        "pct": stage["pct"],
        "purpose": stage["purpose"],
        "target_population": stage["purpose"],
        "window": stage["window"],
        "canary_pct": canary_pct,
        "assets_count": assets_count,
        "selected_count": selected_n,
        "selection_rationale": rationale,
        "selection_criteria": [
            {"factor": "Entorno", "detail": f"{stage['env']} — {'réplica de la infraestructura impactada' if is_replica else 'activos reales'}."},
            {"factor": "Alcance", "detail": scope_txt + "."},
            {"factor": "Orden", "detail": "Los activos se despliegan por dependencia: primero infraestructura, después aplicación y servicio."},
            {"factor": "Pruebas", "detail": "Batería completa de MVT en este entorno." if stage["tests"] else "Validación por telemetría/post-checks (entorno productivo)."},
            {"factor": "Ventana", "detail": stage["window"]},
        ],
        "assets": assets,
        "dependencies": dependencies,
        "graph": {"nodes": graph_nodes, "edges": graph_edges},
        "entry_criteria": entry_criteria,
        "approval": preapproval or {"required": "Human-Driven", "preapproved": False,
                                    "approver": None, "ts": None, "note": None},
    }


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
    """Wrapper de compatibilidad: la simulación vive en `providers.mock_patch`."""
    from .providers.mock_patch import build_ring_actions as _mock_build_ring_actions

    return _mock_build_ring_actions(task, ring_no, assets, executor, ts_base)


def build_rollback_plan(task, impact):
    """Wrapper de compatibilidad: el plan vive en `providers.mock_restore`."""
    from .providers.mock_restore import build_rollback_plan as _mock_build_rollback_plan

    return _mock_build_rollback_plan(task, impact)


CHANGE_TYPE_META = {
    "standard": {
        "label": "Cambio estándar", "itsm_state": "Implement (pre-aprobado)", "requires_human": False,
        "risk": "Bajo", "approval": "Pre-aprobado por modelo de cambio (sin CAB)",
        "detail": "Cambio recurrente, conocido y documentado con procedimiento y riesgo previamente aprobados. Sus fases de autorización están pre-aprobadas por el modelo, por lo que no requiere evaluación individual del CAB. Aplica a lab/desarrollo/pre-producción y actuaciones de bajo riesgo con procedimiento conocido.",
    },
    "normal": {
        "label": "Cambio normal", "itsm_state": "Assess → Authorize", "requires_human": True,
        "risk": "Medio", "approval": "Evaluación y autorización específica (CAB)",
        "detail": "Requiere evaluación y autorización específica antes de ejecutarse; tipología habitual para parcheados que afectan a producción o servicios críticos sin modelo estándar. Recorre todo el proceso: assess, authorize, schedule, authorize implementation, implement y review & close.",
    },
    "emergency": {
        "label": "Cambio de emergencia", "itsm_state": "Emergency authorize", "requires_human": True,
        "risk": "Alto", "approval": "Aprobación express (E-CAB) / regularización posterior",
        "detail": "Intervención urgente ante vulnerabilidad crítica, explotación activa o riesgo inminente; objetivo de remediación en las primeras 24 h. Evaluación, aprobación e implementación aceleradas (E-CAB o mecanismo alternativo); si la urgencia lo impide, autorización excepcional y regularización posterior con revisión obligatoria.",
    },
}

# Fases de la transacción de cambio (ITSM) — "Change Transaction Phases by Change Type".
# Cada tipología recorre un subconjunto distinto; las fases de aprobación son gates.
CHANGE_PHASE_CATALOG = [
    ("new", "Ticket Completion (New)", False),
    ("assess", "Assess", False),
    ("authorize", "Authorize", True),
    ("schedule", "Schedule", False),
    ("authorize_impl", "Authorize Implementation", True),
    ("implement", "Implement", False),
    ("review_close", "Review & Close", False),
]
CHANGE_PHASES_BY_TYPE = {
    # Normal: proceso completo con dos gates de aprobación (Authorize + Authorize Impl.).
    "normal": {"new", "assess", "authorize", "schedule", "authorize_impl", "implement", "review_close"},
    # Estándar pre-autorizado: sin Assess/Authorize/Authorize Impl. (el modelo ya está aprobado).
    "standard": {"new", "schedule", "implement", "review_close"},
    # Emergencia: acelerado; Assess + Authorize (express) y directo a Implement (sin 2º gate).
    "emergency": {"new", "assess", "authorize", "schedule", "implement", "review_close"},
}


def build_itsm_change(task, impact, rng):
    """Registro de cambio en la herramienta ITSM (ServiceNow Change Management)
    asociado a la remediación. Modela las «Change Transaction Phases by Change
    Type»: cada tipología recorre un subconjunto de fases con distintos gates de
    aprobación (fiel al proceso de gestión de cambios del cliente)."""
    ct = task.get("change_type", "normal")
    meta = CHANGE_TYPE_META.get(ct, CHANGE_TYPE_META["normal"])
    chg = f"CHG{rng.randint(100000, 999999)}"
    included = CHANGE_PHASES_BY_TYPE.get(ct, CHANGE_PHASES_BY_TYPE["normal"])
    phases = [{
        "key": key, "label": label, "approval": is_approval,
        "included": key in included,
    } for key, label, is_approval in CHANGE_PHASE_CATALOG]

    # Impacto/riesgo del cambio (criterios de assessment del proceso ITSM).
    bsvc = impact.get("business_services", [])
    crit = task.get("criticality", "medium")
    impact_level = "Alto" if (crit in ("high", "critical") or bsvc) else ("Medio" if crit == "medium" else "Bajo")
    four_eyes = ct != "standard" and (impact_level == "Alto")  # 4-ojos en cambios de mayor impacto
    gxp = bool(bsvc) and crit in ("high", "critical")

    ctasks = [
        {"name": "Assessment (CTASK)", "role": "Técnico L2 — revisa que el cambio está listo para aprobar/implementar",
         "auto": ct == "standard"},
        {"name": "Implementation (CTASK)", "role": f"Ejecutor {_deploy_executor(task, rng)} — aplica el parche según procedimiento", "auto": False},
        {"name": "Review (CTASK)", "role": "Segundo técnico distinto al ejecutor (principio 4-ojos) — confirma el resultado", "auto": False},
    ]
    return {
        "system": "ServiceNow ITSM · Change Management",
        "number": chg,
        "type": ct,
        "type_label": meta["label"],
        "state": meta["itsm_state"],
        "risk": meta["risk"],
        "approval": meta["approval"],
        "requires_human": meta["requires_human"],
        "detail": meta["detail"],
        "short_description": f"Remediación {task['cve']} en {task['ci_name']} ({task.get('component', '-')})",
        "assignment_group": "CAB / Change Management",
        "phases": phases,
        "ctasks": ctasks,
        "four_eyes": four_eyes,
        "gxp": gxp,
        "impact_level": impact_level,
        "affected_cis": impact.get("affected_count", 0),
        "affected_services": bsvc,
        "environment": task.get("environment", "production"),
        "patch": f"{task.get('component', '-')} → {_fixed_version(_prev_version(task))}",
        "vulnerability": task["cve"],
    }


def build_deployment(task, impact, progress_rings: int, rollback=None, rolled_back_rings=None,
                     preapprovals=None, exclusions=None, evidence=None, active_jobs=None):
    """`evidence` contiene, por anillo, las acciones REALES ejecutadas por el
    provider (job). Si existe, prevalece sobre la simulación regenerada, de modo
    que reconstruir el despliegue nunca sobrescribe la evidencia del job."""
    rng = _rng(task["id"] + "deploy")
    evidence = evidence or {}
    active_jobs = active_jobs or {}
    rolled_back_rings = set(rolled_back_rings or [])
    preapprovals = preapprovals or {}
    exclusions = exclusions or {}
    assignment = assign_impact_to_rings(impact)
    total_assets = impact["affected_count"]
    executor = _deploy_executor(task, rng)
    rings = []
    ts_base = 0
    for i, (rn, label) in enumerate(RING_DEFS):
        ring_nodes = assignment.get(rn, [])
        assets = len(ring_nodes)
        if rn in rolled_back_rings:
            status = "rolled_back"
        elif i < progress_rings:
            status = "completed"
        elif i == progress_rings:
            status = "in_progress"
        else:
            status = "pending"
        ring_evidence = evidence.get(rn) or {}
        # Un job AWS ejecuta exactamente una instancia: el conteo mostrado nunca
        # puede ser superior al número de activos realmente ejecutados.
        executed_assets = ring_evidence.get("executed_assets")
        if rn in evidence:
            actions = evidence[rn]
        elif status in ("completed", "rolled_back"):
            actions = build_ring_actions(task, rn, max(1, assets), executor, ts_base)
        else:
            actions = None
        plan = build_ring_plan(task, impact, rn, label, CANARY_PCT[min(i, 4)], executor, ring_nodes,
                               exclusions=exclusions.get(rn), preapproval=preapprovals.get(rn))
        if executed_assets is not None and status in ("completed", "rolled_back"):
            assets = int(executed_assets)
        rings.append({
            "ring": rn, "label": label, "assets": assets, "status": status,
            "executed_assets": executed_assets,
            "post_checks": ["version-assert", "health-check", "smoke-test", "synthetic-probe"] if status in ("completed", "rolled_back") else [],
            "result": {"completed": "healthy", "rolled_back": "reverted", "in_progress": "-", "pending": "-"}[status],
            "actions": actions,
            "plan": plan,
            "job": active_jobs.get(rn),
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
        "strategy": "promoción por entornos (Lab → Canary → Pre-prod → Prod controlado → Prod total)",
        "itsm": build_itsm_change(task, impact, rng),
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
