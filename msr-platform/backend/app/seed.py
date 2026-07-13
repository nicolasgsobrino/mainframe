"""
Generación de datos mock realistas para la plataforma Machine Speed Remediation.

Simula el patrimonio tecnológico de una entidad bancaria (CMDB), un catálogo de
CVEs reales, hallazgos de múltiples escáneres (Qualys/Tenable/SCA/SBOM) y los
registros de ServiceNow (Vulnerable Items, Remediation Tasks). Todo es ficticio y
determinista (semilla fija) para que la demo sea reproducible.
"""
from __future__ import annotations
import random
from datetime import datetime, timedelta

RNG = random.Random(42)
NOW = datetime(2026, 7, 6, 9, 0, 0)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# 1. CMDB — patrimonio bancario (CIs y relaciones)
# ---------------------------------------------------------------------------
# Business services (capa CSDM)
BUSINESS_SERVICES = [
    ("BSVC-0001", "Payments Core", "critical", True),
    ("BSVC-0002", "Retail Banking Web", "critical", True),
    ("BSVC-0003", "Mobile Banking App", "critical", True),
    ("BSVC-0004", "Cards & Authorization", "critical", True),
    ("BSVC-0005", "Fraud Detection", "high", True),
    ("BSVC-0006", "Core Ledger", "critical", True),
    ("BSVC-0007", "Customer CRM", "medium", False),
    ("BSVC-0008", "Regulatory Reporting", "high", True),
    ("BSVC-0009", "Internal Data Warehouse", "medium", False),
    ("BSVC-0010", "Corporate Portal", "low", False),
]

# --- 3 carriles (tracks) de remediación ---
# A · Infraestructura (SO, middleware, runtime, BBDD, red, endpoints) → parche in-place
# B · Aplicaciones y dependencias (código propio, librerías OSS, SBOM) → PR + build + deploy
# C · Contenedores & Cloud-native (imágenes base, K8s, IaC/cloud) → rebuild imagen + rollout
TRACKS = {
    "A": "Infraestructura",
    "B": "Aplicaciones y dependencias",
    "C": "Contenedores & Cloud-native",
}

# Aplicaciones (código propio / COTS)
APPLICATIONS = [
    ("APP-1001", "payments-api", "Java", "BSVC-0001", "B"),
    ("APP-1002", "payments-batch", "Java", "BSVC-0001", "A"),
    ("APP-1003", "retail-web-frontend", "Node", "BSVC-0002", "B"),
    ("APP-1004", "retail-bff", "Node", "BSVC-0002", "C"),
    ("APP-1005", "mobile-gateway", "Java", "BSVC-0003", "B"),
    ("APP-1006", "cards-auth-service", "Java", "BSVC-0004", "B"),
    ("APP-1007", "fraud-scoring-ml", "Python", "BSVC-0005", "C"),
    ("APP-1008", "ledger-core", ".NET", "BSVC-0006", "A"),
    ("APP-1009", "crm-portal", ".NET", "BSVC-0007", "A"),
    ("APP-1010", "regulatory-reporter", "Java", "BSVC-0008", "B"),
    ("APP-1011", "dwh-etl", "Python", "BSVC-0009", "C"),
    ("APP-1012", "corp-portal-cms", "PHP", "BSVC-0010", "A"),
]

# Bases de datos
DATABASES = [
    ("DB-2001", "Oracle 19c", "oracle", "BSVC-0001"),
    ("DB-2002", "Oracle 19c", "oracle", "BSVC-0006"),
    ("DB-2003", "SQL Server 2019", "mssql", "BSVC-0004"),
    ("DB-2004", "PostgreSQL 14", "postgres", "BSVC-0002"),
    ("DB-2005", "PostgreSQL 13", "postgres", "BSVC-0005"),
    ("DB-2006", "SQL Server 2017", "mssql", "BSVC-0007"),
    ("DB-2007", "Oracle 12c", "oracle", "BSVC-0008"),
]

# Middleware / runtime instalados en servidores
MIDDLEWARE_TYPES = ["Apache Tomcat 9", "Oracle WebLogic 14", "Nginx 1.24", "IIS 10", "Apache HTTPD 2.4"]
RUNTIME_TYPES = ["OpenJDK 11", "OpenJDK 17", ".NET 6", "Node 18", "Python 3.10"]

OS_TYPES = [
    ("RHEL 8.8", "linux"),
    ("RHEL 9.2", "linux"),
    ("Windows Server 2019", "windows"),
    ("Windows Server 2022", "windows"),
    ("Ubuntu 22.04", "linux"),
]
ENVIRONMENTS = ["production", "pre-production", "development"]
LOCATIONS = ["DC-Madrid", "DC-Barcelona", "AWS eu-west-1", "Azure West Europe"]
OWNERS = [
    "infra-linux@bank.example", "infra-windows@bank.example", "dba-team@bank.example",
    "payments-squad@bank.example", "retail-squad@bank.example", "cards-squad@bank.example",
    "fraud-squad@bank.example", "platform-team@bank.example", "appsec@bank.example",
]


# --- Modelo CMDB estandarizado (alineado con ServiceNow CSDM) ---
CMDB_SOURCE = "ServiceNow CMDB (CSDM 4.0)"
SYS_CLASS = {
    "business_service": "cmdb_ci_service",
    "application": "cmdb_ci_appl",
    "database": "cmdb_ci_database",
    "server": "cmdb_ci_server",
    "middleware": "cmdb_ci_app_server",
    "runtime": "cmdb_ci_runtime",
    "container": "cmdb_ci_docker_container",
    "network_device": "cmdb_ci_netgear",
    "endpoint": "cmdb_ci_computer",
    "cloud_resource": "cmdb_ci_cloud_resource",
}
CRIT_TIER = {
    "critical": "1 - most critical",
    "high": "2 - somewhat critical",
    "medium": "3 - less critical",
    "low": "4 - not critical",
}
# Track por clase de CI (los infra van al carril A, contenedores/cloud al C)
CLASS_TRACK = {
    "server": "A", "middleware": "A", "runtime": "A", "database": "A",
    "network_device": "A", "endpoint": "A",
    "container": "C", "cloud_resource": "C",
}
SUPPORT_GROUPS = [
    "SG-Infra-Linux", "SG-Infra-Windows", "SG-DBA", "SG-Network", "SG-Endpoint",
    "SG-Platform-K8s", "SG-Cloud-FinOps", "SG-AppSec", "SG-Payments", "SG-Retail",
]


def _std_fields(ci):
    """Añade los campos estandarizados (CSDM) que llegarían de una CMDB real."""
    crit = ci.get("criticality", "medium")
    cls = ci["ci_class"]
    ci.setdefault("sys_class_name", SYS_CLASS.get(cls, "cmdb_ci"))
    ci.setdefault("install_status", "Installed")
    ci.setdefault("business_criticality", CRIT_TIER.get(crit, CRIT_TIER["medium"]))
    ci.setdefault("cmdb_source", CMDB_SOURCE)
    if "track" not in ci and cls in CLASS_TRACK:
        ci["track"] = CLASS_TRACK[cls]
    if "support_group" not in ci:
        og = ci.get("owner", "")
        if "linux" in og:
            ci["support_group"] = "SG-Infra-Linux"
        elif "windows" in og:
            ci["support_group"] = "SG-Infra-Windows"
        elif "dba" in og:
            ci["support_group"] = "SG-DBA"
        else:
            ci["support_group"] = RNG.choice(SUPPORT_GROUPS)
    return ci


def build_cmdb():
    cis = []
    edges = []

    for sid, name, crit, dora in BUSINESS_SERVICES:
        cis.append({
            "id": sid, "name": name, "ci_class": "business_service",
            "criticality": crit, "environment": "production", "dora_relevant": dora,
            "owner": "service-owner@bank.example", "location": "-", "version": "-",
        })

    # Servers host apps / dbs / middleware
    server_idx = 3000
    for app_id, app_name, tech, bsvc, track in APPLICATIONS:
        n_servers = RNG.choice([2, 2, 3, 4])
        os_name, os_family = RNG.choice(OS_TYPES)
        owner = RNG.choice(OWNERS)
        cis.append({
            "id": app_id, "name": app_name, "ci_class": "application",
            "criticality": next(b[2] for b in BUSINESS_SERVICES if b[0] == bsvc),
            "environment": "production", "tech": tech, "track": track,
            "owner": owner, "location": "-", "version": f"{RNG.randint(2,8)}.{RNG.randint(0,9)}.{RNG.randint(0,9)}",
            "repo": f"bank-org/{app_name}", "dora_relevant": next(b[3] for b in BUSINESS_SERVICES if b[0] == bsvc),
        })
        edges.append({"source": app_id, "target": bsvc, "type": "supports"})

        for _ in range(n_servers):
            sid = f"SRV-{server_idx}"; server_idx += 1
            os_name2, os_family2 = RNG.choice(OS_TYPES)
            cis.append({
                "id": sid, "name": f"{app_name}-{RNG.choice(['app','web','node'])}-{RNG.randint(1,9):02d}",
                "ci_class": "server", "os": os_name2, "os_family": os_family2,
                "criticality": next(b[2] for b in BUSINESS_SERVICES if b[0] == bsvc),
                "environment": RNG.choice(["production", "production", "pre-production"]),
                "owner": "infra-linux@bank.example" if os_family2 == "linux" else "infra-windows@bank.example",
                "location": RNG.choice(LOCATIONS),
                "version": os_name2, "maintenance_window": RNG.choice(["Sat 02:00-06:00", "Sun 01:00-05:00", "Daily 03:00-04:00"]),
            })
            edges.append({"source": sid, "target": app_id, "type": "runs"})
            # middleware + runtime on the server
            mw = RNG.choice(MIDDLEWARE_TYPES)
            rt = RNG.choice(RUNTIME_TYPES)
            cis.append({"id": f"MW-{server_idx}", "name": mw, "ci_class": "middleware",
                        "criticality": "medium", "environment": "production", "owner": "platform-team@bank.example",
                        "location": "-", "version": mw})
            edges.append({"source": f"MW-{server_idx}", "target": sid, "type": "installed_on"}); server_idx += 1
            cis.append({"id": f"RT-{server_idx}", "name": rt, "ci_class": "runtime",
                        "criticality": "medium", "environment": "production", "owner": "platform-team@bank.example",
                        "location": "-", "version": rt})
            edges.append({"source": f"RT-{server_idx}", "target": sid, "type": "installed_on"}); server_idx += 1

    # Databases host on servers and support services
    for db_id, db_name, engine, bsvc in DATABASES:
        sid = f"SRV-{server_idx}"; server_idx += 1
        os_name2, os_family2 = ("RHEL 8.8", "linux") if engine in ("oracle", "postgres") else ("Windows Server 2019", "windows")
        cis.append({
            "id": sid, "name": f"db-{engine}-{RNG.randint(1,9):02d}", "ci_class": "server",
            "os": os_name2, "os_family": os_family2, "criticality": "critical",
            "environment": "production", "owner": "dba-team@bank.example",
            "location": RNG.choice(LOCATIONS), "version": os_name2,
            "maintenance_window": "Sun 01:00-05:00",
        })
        cis.append({"id": db_id, "name": db_name, "ci_class": "database", "engine": engine,
                    "criticality": "critical", "environment": "production", "owner": "dba-team@bank.example",
                    "location": "-", "version": db_name})
        edges.append({"source": db_id, "target": sid, "type": "hosted_on"})
        edges.append({"source": db_id, "target": bsvc, "type": "supports"})

    # -----------------------------------------------------------------
    # Escalado a ~10.000 CIs con patrimonio sintético (granja de servidores,
    # contenedores, red, endpoints y recursos cloud) manteniendo el modelo CSDM.
    # -----------------------------------------------------------------
    cis, edges = _scale_estate(cis, edges, target=10000)

    # Normalización final: todos los CIs con campos estandarizados (CSDM).
    for c in cis:
        _std_fields(c)
    return cis, edges


CONTAINER_IMAGES = [
    "eclipse-temurin:17-jre", "node:18-alpine", "python:3.11-slim", "nginx:1.25",
    "openjdk:11-jre", "redis:7", "postgres:15", "amazoncorretto:17", "distroless/java17",
]
CLOUD_KINDS = [
    ("AWS Lambda", "aws"), ("EKS Node Group", "aws"), ("Azure Function", "azure"),
    ("AKS Node Pool", "azure"), ("S3 Bucket Policy", "aws"), ("RDS Instance", "aws"),
    ("API Gateway", "aws"), ("Azure App Service", "azure"),
]
NET_KINDS = ["Cisco Catalyst 9300", "Fortinet FortiGate 600F", "F5 BIG-IP i5800",
             "Palo Alto PA-5450", "Juniper MX204", "Cisco Nexus 9508"]


def _scale_estate(cis, edges, target=10000):
    """Genera CIs sintéticos hasta alcanzar ~`target`, con relaciones realistas."""
    apps = [c for c in cis if c["ci_class"] == "application"]
    services = [c for c in cis if c["ci_class"] == "business_service"]
    crit_choices = ["critical", "high", "high", "medium", "medium", "medium", "low"]
    env_choices = ["production", "production", "production", "pre-production", "development"]
    idx = 40000

    def nid(prefix):
        nonlocal idx
        idx += 1
        return f"{prefix}-{idx}"

    while len(cis) < target:
        roll = RNG.random()
        crit = RNG.choice(crit_choices)
        env = RNG.choice(env_choices)
        loc = RNG.choice(LOCATIONS)
        if roll < 0.42:
            # servidor (carril A)
            os_name, fam = RNG.choice(OS_TYPES)
            cid = nid("SRV")
            cis.append({"id": cid, "name": f"srv-{fam}-{idx}", "ci_class": "server",
                        "os": os_name, "os_family": fam, "criticality": crit, "environment": env,
                        "owner": "infra-linux@bank.example" if fam == "linux" else "infra-windows@bank.example",
                        "location": loc, "version": os_name,
                        "maintenance_window": RNG.choice(["Sat 02:00-06:00", "Sun 01:00-05:00", "Daily 03:00-04:00"])})
            if apps and RNG.random() < 0.6:
                app = RNG.choice(apps)
                edges.append({"source": cid, "target": app["id"], "type": "runs"})
            # a veces middleware/runtime encima
            if RNG.random() < 0.5:
                mid = nid("MW")
                cis.append({"id": mid, "name": RNG.choice(MIDDLEWARE_TYPES), "ci_class": "middleware",
                            "criticality": crit, "environment": env, "owner": "platform-team@bank.example",
                            "location": loc, "version": "-"})
                edges.append({"source": mid, "target": cid, "type": "installed_on"})
            if RNG.random() < 0.5 and len(cis) < target:
                rt = nid("RT")
                cis.append({"id": rt, "name": RNG.choice(RUNTIME_TYPES), "ci_class": "runtime",
                            "criticality": crit, "environment": env, "owner": "platform-team@bank.example",
                            "location": loc, "version": "-"})
                edges.append({"source": rt, "target": cid, "type": "installed_on"})
        elif roll < 0.62:
            # contenedor (carril C)
            cid = nid("CNT")
            img = RNG.choice(CONTAINER_IMAGES)
            cis.append({"id": cid, "name": f"pod/{img.split(':')[0].split('/')[-1]}-{idx}", "ci_class": "container",
                        "criticality": crit, "environment": env, "owner": "platform-team@bank.example",
                        "location": RNG.choice(["EKS eu-west-1", "AKS West Europe", "OpenShift DC-Madrid"]),
                        "version": img, "track": "C", "image": img})
            if apps and RNG.random() < 0.7:
                app = RNG.choice(apps)
                edges.append({"source": cid, "target": app["id"], "type": "runs"})
        elif roll < 0.74:
            # endpoint / workstation (carril A)
            cid = nid("EP")
            cis.append({"id": cid, "name": f"WKS-{RNG.choice(['MAD','BCN','VAL'])}-{idx}", "ci_class": "endpoint",
                        "criticality": "low" if RNG.random() < 0.8 else "medium", "environment": "production",
                        "owner": "endpoint-team@bank.example", "location": loc,
                        "version": RNG.choice(["Windows 11 23H2", "macOS 14", "Windows 10 22H2"])})
        elif roll < 0.84:
            # recurso cloud (carril C)
            kind, cloud = RNG.choice(CLOUD_KINDS)
            cid = nid("CLD")
            cis.append({"id": cid, "name": f"{kind} · {cloud}-{idx}", "ci_class": "cloud_resource",
                        "criticality": crit, "environment": env, "owner": "SG-Cloud-FinOps",
                        "location": "AWS eu-west-1" if cloud == "aws" else "Azure West Europe",
                        "version": kind, "track": "C", "cloud": cloud})
            if apps and RNG.random() < 0.5:
                edges.append({"source": cid, "target": RNG.choice(apps)["id"], "type": "supports"})
        elif roll < 0.90:
            # dispositivo de red (carril A)
            cid = nid("NET")
            cis.append({"id": cid, "name": f"{RNG.choice(NET_KINDS)} #{idx}", "ci_class": "network_device",
                        "criticality": crit, "environment": "production", "owner": "network-team@bank.example",
                        "location": loc, "version": RNG.choice(["17.9", "7.4", "16.1", "11.1"])})
        else:
            # aplicación adicional (carril A/B/C)
            track = RNG.choice(["A", "B", "B", "C"])
            svc = RNG.choice(services) if services else None
            cid = nid("APP")
            tech = RNG.choice(["Java", "Node", "Python", ".NET", "Go"])
            cis.append({"id": cid, "name": f"svc-{tech.lower()}-{idx}", "ci_class": "application",
                        "criticality": svc["criticality"] if svc else crit, "environment": env, "tech": tech,
                        "track": track, "owner": RNG.choice(OWNERS), "location": "-",
                        "version": f"{RNG.randint(1,9)}.{RNG.randint(0,9)}.{RNG.randint(0,9)}",
                        "repo": f"bank-org/svc-{tech.lower()}-{idx}",
                        "dora_relevant": bool(svc and svc.get("dora_relevant"))})
            if svc:
                edges.append({"source": cid, "target": svc["id"], "type": "supports"})
                apps.append(cis[-1])
    return cis, edges


# ---------------------------------------------------------------------------
# 2. Catálogo de CVEs (realistas)
# ---------------------------------------------------------------------------
CVE_CATALOG = [
    # cve, title, cvss, epss, kev, exploit, track, affected, package/component
    ("CVE-2021-44228", "Apache Log4j2 JNDI RCE (Log4Shell)", 10.0, 0.975, True, True, "B", "log4j-core", "2.14.1"),
    ("CVE-2022-22965", "Spring Framework RCE (Spring4Shell)", 9.8, 0.943, True, True, "B", "spring-beans", "5.3.17"),
    ("CVE-2022-1471", "SnakeYAML Deserialization RCE", 9.8, 0.61, False, True, "B", "snakeyaml", "1.30"),
    ("CVE-2023-4863", "libwebp Heap Buffer Overflow", 8.8, 0.71, True, True, "C", "libwebp", "1.2.4"),
    ("CVE-2023-44487", "HTTP/2 Rapid Reset DoS", 7.5, 0.88, True, True, "A", "nginx", "1.24.0"),
    ("CVE-2024-3094", "XZ Utils Backdoor", 10.0, 0.42, True, True, "A", "xz-utils", "5.6.0"),
    ("CVE-2023-50164", "Apache Struts Path Traversal RCE", 9.8, 0.66, True, True, "B", "struts2-core", "2.5.30"),
    ("CVE-2022-42889", "Apache Commons Text RCE (Text4Shell)", 9.8, 0.55, False, True, "B", "commons-text", "1.9"),
    ("CVE-2023-34362", "MOVEit Transfer SQLi RCE", 9.8, 0.94, True, True, "A", "MOVEit Transfer", "15.0"),
    ("CVE-2021-34527", "Windows Print Spooler RCE (PrintNightmare)", 8.8, 0.72, True, True, "A", "Windows Spooler", "-"),
    ("CVE-2024-21626", "runc Container Escape", 8.6, 0.15, False, True, "C", "runc", "1.1.11"),
    ("CVE-2023-22515", "Atlassian Confluence Priv Esc", 9.8, 0.90, True, True, "A", "Confluence", "8.5.1"),
    ("CVE-2022-3602", "OpenSSL X.509 Buffer Overflow", 7.5, 0.20, False, False, "A", "openssl", "3.0.6"),
    ("CVE-2023-38545", "curl SOCKS5 Heap Overflow", 8.8, 0.18, False, False, "A", "curl", "8.3.0"),
    ("CVE-2024-6387", "OpenSSH regreSSHion RCE", 8.1, 0.36, True, True, "A", "openssh-server", "9.6"),
    ("CVE-2022-1388", "F5 BIG-IP iControl REST Auth Bypass", 9.8, 0.91, True, True, "A", "BIG-IP", "16.1"),
    ("CVE-2023-2033", "Chromium V8 Type Confusion", 8.8, 0.12, True, True, "A", "chromium", "112.0"),
    ("CVE-2021-45046", "Log4j2 incomplete fix RCE", 9.0, 0.80, True, True, "B", "log4j-core", "2.15.0"),
    ("CVE-2024-27198", "TeamCity Auth Bypass", 9.8, 0.88, True, True, "A", "TeamCity", "2023.11"),
    ("CVE-2023-46604", "Apache ActiveMQ RCE", 10.0, 0.94, True, True, "B", "activemq", "5.18.2"),
    ("CVE-2022-40684", "Fortinet Auth Bypass", 9.8, 0.86, True, True, "A", "FortiOS", "7.2"),
    ("CVE-2023-20198", "Cisco IOS XE Web UI Priv Esc", 10.0, 0.93, True, True, "A", "IOS XE", "17.9"),
    ("CVE-2024-1709", "ConnectWise ScreenConnect Auth Bypass", 10.0, 0.94, True, True, "A", "ScreenConnect", "23.9"),
    ("CVE-2020-1472", "Netlogon Priv Esc (Zerologon)", 10.0, 0.70, True, True, "A", "Windows Netlogon", "-"),
    ("CVE-2022-23648", "containerd Host File Access", 7.5, 0.30, False, True, "C", "containerd", "1.5.9"),
    ("CVE-2021-25741", "Kubernetes kubelet Path Traversal", 8.1, 0.25, False, True, "C", "kubelet", "1.21.0"),
    ("CVE-2023-5044", "Ingress-NGINX Annotation Injection", 7.6, 0.28, False, True, "C", "ingress-nginx", "1.8.0"),
]


# ---------------------------------------------------------------------------
# 3. Hallazgos, Vulnerable Items y Remediation Tasks
# ---------------------------------------------------------------------------
SCANNERS = ["Qualys VMDR", "Tenable.io", "Microsoft Defender", "Snyk (SCA)", "Wiz (CSPM)", "SBOM (Syft)"]


def _risk_score(cvss, epss, kev, exposed, criticality, env):
    """Prioridad final = riesgo técnico + negocio + operativo + SLA (0-100)."""
    tech = cvss * 4  # 0-40
    exploit = (epss * 20) + (12 if kev else 0)  # 0-32
    business = {"critical": 18, "high": 12, "medium": 6, "low": 2}[criticality]
    exposure = 10 if exposed else 0
    env_factor = 0 if env == "production" else (-8 if env == "development" else -4)
    return round(min(100, max(0, tech + exploit + business + exposure + env_factor)))


def build_records(cis, edges):
    servers = [c for c in cis if c["ci_class"] == "server"]
    apps = [c for c in cis if c["ci_class"] == "application"]
    findings = []
    fid = 500000

    # Generamos muchos hallazgos brutos (simula el embudo 100k → ...)
    for _ in range(240):
        cve = RNG.choice(CVE_CATALOG)
        target_pool = apps if cve[6] == "B" else servers
        ci = RNG.choice(target_pool)
        fid += 1
        findings.append({
            "id": f"FND{fid}", "cve": cve[0], "scanner": RNG.choice(SCANNERS),
            "ci_id": ci["id"], "ci_name": ci["name"], "detected_at": iso(NOW - timedelta(days=RNG.randint(0, 20))),
            "raw_severity": cve[2],
        })

    # Curamos un conjunto de Vulnerable Items (los que avanzan a Remediation Task)
    def ci_of_class(cls):
        return [c for c in cis if c["ci_class"] == cls]

    # Definimos escenarios de demo concretos y potentes
    scenarios = [
        # (cve_index, ci_id preferido o None, exposed, phase, ring_progress)
        (0, "APP-1001", True),   # Log4Shell en payments-api (Track B, crítico)
        (1, "APP-1005", True),   # Spring4Shell en mobile-gateway
        (5, None, False),        # XZ backdoor en server (Track A)
        (14, None, True),        # regreSSHion OpenSSH (Track A)
        (9, None, False),        # PrintNightmare (Track A Windows)
        (19, "APP-1010", False), # ActiveMQ RCE regulatory-reporter (Track B)
        (2, "APP-1006", True),   # SnakeYAML cards-auth (Track B)
        (4, None, True),         # HTTP/2 Rapid Reset nginx (Track A)
        (7, "APP-1003", True),   # Text4Shell retail-web (Track B)
        (23, None, False),       # Zerologon (Track A)
        (6, "APP-1001", True),   # Struts payments (Track B)
        (12, None, False),       # OpenSSL (Track A, baja)
        (10, "APP-1004", False), # runc Container Escape en retail-bff (Track C)
        (24, "APP-1007", True),  # containerd Host File Access en fraud-scoring-ml (Track C)
        (3, "APP-1011", False),  # libwebp en dwh-etl (Track C)
    ]

    vitems = []
    tasks = []
    vid = 700000
    tid = 900000
    for idx, (cve_i, pref_ci, exposed) in enumerate(scenarios):
        cve = CVE_CATALOG[cve_i]
        track = cve[6]
        if pref_ci:
            ci = next(c for c in cis if c["id"] == pref_ci)
        else:
            ci = RNG.choice(servers)
        env = ci.get("environment", "production")
        crit = ci.get("criticality", "medium")
        risk = _risk_score(cve[2], cve[3], cve[4], exposed, crit, env)
        vid += 1
        vitem = {
            "id": f"VIT{vid}", "cve": cve[0], "title": cve[1], "cvss": cve[2], "epss": cve[3],
            "kev": cve[4], "exploit_available": cve[5], "track": track, "component": cve[7],
            "vulnerable_version": cve[8], "ci_id": ci["id"], "ci_name": ci["name"],
            "ci_class": ci["ci_class"], "exposed": exposed, "criticality": crit,
            "environment": env, "owner": ci.get("owner", RNG.choice(OWNERS)),
            "risk_score": risk, "sources": RNG.sample(SCANNERS, RNG.randint(1, 3)),
            "status": "open", "detected_at": iso(NOW - timedelta(days=RNG.randint(1, 15))),
        }
        # SLA por severidad/KEV
        if cve[4] or cve[2] >= 9:
            sla_days = 3
        elif cve[2] >= 7:
            sla_days = 15
        else:
            sla_days = 30
        vitem["sla_days"] = sla_days
        vitem["sla_due"] = iso(NOW + timedelta(days=sla_days - RNG.randint(0, 2)))
        vitems.append(vitem)

        tid += 1
        change_type = "emergency" if risk >= 80 else ("normal" if risk >= 50 else "standard")
        tasks.append({
            "id": f"RTASK{tid}", "vulnerable_item_id": vitem["id"], "cve": cve[0], "title": cve[1],
            "track": track, "risk_score": risk, "priority": _priority_label(risk),
            "ci_id": ci["id"], "ci_name": ci["name"], "owner": vitem["owner"],
            "criticality": crit, "environment": env, "sla_due": vitem["sla_due"],
            "change_type": change_type, "exposed": exposed, "component": cve[7],
            "vulnerable_version": cve[8], "created_at": iso(NOW - timedelta(days=RNG.randint(0, 8))),
        })

    return findings, vitems, tasks


def _priority_label(risk):
    if risk >= 80:
        return "critical"
    if risk >= 60:
        return "high"
    if risk >= 40:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# 4. Catálogo de pruebas (versionado en Git)
# ---------------------------------------------------------------------------
TEST_CATALOG = [
    # id, name, layer, applies_to (ci_class/tech), remediation_type, criticality, tool, evidence
    ("TC-OS-001", "Host health & uptime check", "os", "server", "patch", "any", "Ansible", "log"),
    ("TC-OS-002", "Package/patch version assertion", "os", "server", "patch", "any", "Ansible", "log"),
    ("TC-OS-003", "Service status post-reboot", "os", "server", "patch", "any", "Ansible", "log"),
    ("TC-OS-004", "Reboot & boot validation", "os", "server", "patch", "high", "Ansible", "log"),
    ("TC-OS-005", "Network connectivity check", "os", "server", "patch", "any", "Ansible", "log"),
    ("TC-DB-001", "Oracle listener availability", "database", "oracle", "patch", "any", "pytest", "log"),
    ("TC-DB-002", "DB connection & smoke query", "database", "oracle", "patch", "any", "pytest", "screenshot"),
    ("TC-DB-003", "SQL Server availability group check", "database", "mssql", "patch", "high", "pytest", "log"),
    ("TC-DB-004", "PostgreSQL replication lag check", "database", "postgres", "patch", "high", "pytest", "metric"),
    ("TC-MW-001", "Tomcat manager health", "middleware", "middleware", "patch", "any", "pytest", "log"),
    ("TC-MW-002", "WebLogic managed server status", "middleware", "middleware", "patch", "high", "pytest", "log"),
    ("TC-RT-001", "JVM startup & version check", "runtime", "runtime", "patch", "any", "pytest", "log"),
    ("TC-APP-001", "Application smoke test", "application", "application", "any", "any", "Playwright", "screenshot"),
    ("TC-APP-002", "REST API contract test", "application", "application", "any", "any", "Postman/Newman", "report"),
    ("TC-APP-003", "App→DB connectivity", "application", "application", "any", "high", "pytest", "log"),
    ("TC-APP-004", "Critical user journey (E2E)", "application", "application", "any", "critical", "Playwright", "video"),
    ("TC-APP-005", "Selective regression suite", "application", "application", "dependency", "high", "JUnit", "report"),
    ("TC-APP-006", "Dependency SCA re-scan", "application", "application", "dependency", "any", "Snyk", "report"),
    ("TC-EXT-001", "External synthetic endpoint probe", "external", "business_service", "any", "critical", "Datadog Synthetics", "metric"),
    ("TC-EXT-002", "TLS/cert validation", "external", "business_service", "any", "high", "testssl.sh", "report"),
]


def build_all():
    cis, edges = build_cmdb()
    findings, vitems, tasks = build_records(cis, edges)
    catalog = [dict(zip(
        ["id", "name", "layer", "applies_to", "remediation_type", "criticality", "tool", "evidence"], t))
        for t in TEST_CATALOG]
    return {
        "cis": cis, "edges": edges, "findings": findings,
        "vulnerable_items": vitems, "remediation_tasks": tasks, "test_catalog": catalog,
    }
