"""Descubrimiento de red de sólo lectura previo al primer `terraform apply`.

    python -m app.net_discovery                 # informe en Markdown
    python -m app.net_discovery --json          # el mismo informe en JSON

Sólo se invocan APIs `Describe*` de EC2: el módulo no crea, modifica ni elimina
ningún recurso, no inicia ninguna Automation y no toca el laboratorio. Su salida
alimenta la selección de subnets del ALB y la resolución de la salida de las
tasks de Fargate; nada se elige automáticamente por el simple hecho de existir.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import ConfigurationError, Settings, get_settings

log = logging.getLogger("msr.net.discovery")

# IPs libres mínimas para colocar dos ENIs del ALB más las de las tasks.
MIN_FREE_IPS_FOR_ALB = 8
MIN_FREE_IPS_FOR_TASKS = 4

# Endpoints de VPC que necesitaría el backend si sus subnets no tienen NAT.
REQUIRED_ENDPOINT_SERVICES = (
    "ecr.api",
    "ecr.dkr",
    "s3",
    "logs",
    "ssm",
    "ssmmessages",
    "ec2",
    "autoscaling",
    "dynamodb",
)

# Destinos de ruta reconocidos, en el orden en que se informan.
ROUTE_TARGET_KEYS = (
    ("GatewayId", "gateway"),
    ("NatGatewayId", "nat-gateway"),
    ("TransitGatewayId", "transit-gateway"),
    ("VpcPeeringConnectionId", "vpc-peering"),
    ("NetworkInterfaceId", "network-interface"),
    ("InstanceId", "instance"),
    ("CarrierGatewayId", "carrier-gateway"),
    ("EgressOnlyInternetGatewayId", "egress-only-internet-gateway"),
    ("LocalGatewayId", "local-gateway"),
    ("CoreNetworkArn", "core-network"),
)

DEFAULT_ROUTES = ("0.0.0.0/0", "::/0")


def _tag(resource: dict, key: str) -> str:
    for tag in resource.get("Tags") or []:
        if tag.get("Key") == key:
            return str(tag.get("Value") or "")
    return ""


def route_target(route: dict) -> dict:
    """Destino de una ruta, normalizado a un tipo comprensible."""
    for field, kind in ROUTE_TARGET_KEYS:
        value = route.get(field)
        if not value:
            continue
        if field == "GatewayId":
            if value == "local":
                kind = "local"
            elif value.startswith("igw-"):
                kind = "internet-gateway"
            elif value.startswith("vpce-"):
                kind = "gateway-vpc-endpoint"
            elif value.startswith("vgw-"):
                kind = "virtual-private-gateway"
        return {
            "destination": (route.get("DestinationCidrBlock")
                            or route.get("DestinationIpv6CidrBlock")
                            or route.get("DestinationPrefixListId") or ""),
            "target": str(value),
            "kind": kind,
            "state": str(route.get("State") or ""),
        }
    return {
        "destination": str(route.get("DestinationCidrBlock") or ""),
        "target": "",
        "kind": "unknown",
        "state": str(route.get("State") or ""),
    }


def route_table_for_subnet(subnet_id: str, route_tables: list[dict]) -> dict | None:
    """Tabla asociada explícitamente a la subnet o, si no hay, la principal."""
    main_table = None
    for table in route_tables:
        for association in table.get("Associations") or []:
            if association.get("SubnetId") == subnet_id:
                return table
            if association.get("Main"):
                main_table = table
    return main_table


def subnet_routing(subnet_id: str, route_tables: list[dict]) -> dict:
    """Rutas efectivas de la subnet y por dónde sale su tráfico por defecto."""
    table = route_table_for_subnet(subnet_id, route_tables)
    if table is None:
        return {"route_table_id": "", "is_main_table": False, "routes": [],
                "default_route_kind": "none", "default_route_target": "",
                "egress": "none"}
    routes = [route_target(route) for route in table.get("Routes") or []]
    default = next(
        (route for route in routes
         if route["destination"] in DEFAULT_ROUTES and route["kind"] != "local"),
        None,
    )
    kind = default["kind"] if default else "none"
    egress = {
        "internet-gateway": "internet-gateway",
        "nat-gateway": "nat-gateway",
        "transit-gateway": "transit-gateway",
        "virtual-private-gateway": "virtual-private-gateway",
        "core-network": "core-network",
        "vpc-peering": "vpc-peering",
    }.get(kind, "none")
    is_main = any(association.get("Main")
                  for association in table.get("Associations") or [])
    return {
        "route_table_id": str(table.get("RouteTableId") or ""),
        "is_main_table": is_main,
        "routes": routes,
        "default_route_kind": kind,
        "default_route_target": default["target"] if default else "",
        "egress": egress,
    }


def endpoint_coverage(endpoints: list[dict], region: str) -> dict:
    """Endpoints de VPC presentes, por servicio requerido."""
    coverage: dict[str, dict] = {}
    for service in REQUIRED_ENDPOINT_SERVICES:
        name = f"com.amazonaws.{region}.{service}"
        matches = [endpoint for endpoint in endpoints
                   if str(endpoint.get("ServiceName") or "") == name]
        coverage[service] = {
            "service_name": name,
            "present": bool(matches),
            "ids": [str(match.get("VpcEndpointId") or "") for match in matches],
            "types": sorted({str(match.get("VpcEndpointType") or "") for match in matches}),
            "subnet_ids": sorted({subnet for match in matches
                                  for subnet in match.get("SubnetIds") or []}),
            "states": sorted({str(match.get("State") or "") for match in matches}),
        }
    return coverage


def classify_subnet(subnet: dict, routing: dict, coverage: dict) -> dict:
    """Aptitud de la subnet para el ALB interno y para las tasks de Fargate."""
    free_ips = int(subnet.get("AvailableIpAddressCount") or 0)
    public = routing["egress"] == "internet-gateway"
    endpoints_complete = all(item["present"] for item in coverage.values())
    task_egress = routing["egress"] in ("nat-gateway", "transit-gateway",
                                        "virtual-private-gateway", "core-network")

    alb_reasons: list[str] = []
    if public:
        alb_reasons.append("default route to an Internet Gateway: it is a public subnet, "
                           "only valid for an internet-facing ALB")
    if free_ips < MIN_FREE_IPS_FOR_ALB:
        alb_reasons.append(f"only {free_ips} free IPs (minimum {MIN_FREE_IPS_FOR_ALB})")

    task_reasons: list[str] = []
    if free_ips < MIN_FREE_IPS_FOR_TASKS:
        task_reasons.append(f"only {free_ips} free IPs (minimum {MIN_FREE_IPS_FOR_TASKS})")
    if not task_egress and not endpoints_complete:
        missing = sorted(service for service, item in coverage.items() if not item["present"])
        task_reasons.append("no NAT/Transit Gateway and no VPC endpoints for: "
                            + ", ".join(missing))

    return {
        "subnet_id": str(subnet.get("SubnetId") or ""),
        "name": _tag(subnet, "Name"),
        "availability_zone": str(subnet.get("AvailabilityZone") or ""),
        "cidr_block": str(subnet.get("CidrBlock") or ""),
        "available_ip_count": free_ips,
        "map_public_ip_on_launch": bool(subnet.get("MapPublicIpOnLaunch")),
        "is_public": public,
        "routing": routing,
        "suitable_for_internal_alb": not alb_reasons,
        "suitable_for_fargate_tasks": not task_reasons,
        "alb_blockers": alb_reasons,
        "task_blockers": task_reasons,
    }


def propose_subnets(subnets: list[dict], key: str) -> list[str]:
    """Una subnet apta por zona: el ALB exige al menos dos zonas distintas.

    No se propone nada por el mero hecho de existir: sólo entran las subnets que
    han superado la clasificación, y la elección definitiva la valida el equipo
    de red.
    """
    chosen: dict[str, str] = {}
    for subnet in sorted(subnets, key=lambda item: (item["availability_zone"],
                                                    -item["available_ip_count"])):
        if not subnet[key]:
            continue
        chosen.setdefault(subnet["availability_zone"], subnet["subnet_id"])
    return [chosen[zone] for zone in sorted(chosen)]


def _paginate(client, operation: str, result_key: str, **kwargs) -> list[dict]:
    paginator = client.get_paginator(operation)
    items: list[dict] = []
    for page in paginator.paginate(**kwargs):
        items.extend(page.get(result_key) or [])
    return items


def _vpc_attribute(client, vpc_id: str, attribute: str) -> bool | None:
    response = client.describe_vpc_attribute(VpcId=vpc_id, Attribute=attribute)
    value = response.get(attribute[0].upper() + attribute[1:]) or {}
    return value.get("Value")


def discover(client, vpc_id: str, region: str) -> dict:
    """Informe de red de la VPC indicada. Todas las llamadas son `Describe*`."""
    vpcs = _paginate(client, "describe_vpcs", "Vpcs", VpcIds=[vpc_id])
    if not vpcs:
        raise ConfigurationError(f"VPC {vpc_id} does not exist in {region}.")
    vpc = vpcs[0]

    filters = [{"Name": "vpc-id", "Values": [vpc_id]}]
    subnets = _paginate(client, "describe_subnets", "Subnets", Filters=filters)
    route_tables = _paginate(client, "describe_route_tables", "RouteTables", Filters=filters)
    endpoints = _paginate(client, "describe_vpc_endpoints", "VpcEndpoints", Filters=filters)
    nat_gateways = _paginate(client, "describe_nat_gateways", "NatGateways",
                             Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
    gateways = _paginate(client, "describe_internet_gateways", "InternetGateways",
                         Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}])

    coverage = endpoint_coverage(endpoints, region)
    classified = [
        classify_subnet(subnet, subnet_routing(str(subnet.get("SubnetId") or ""), route_tables),
                        coverage)
        for subnet in subnets
    ]
    classified.sort(key=lambda item: (item["availability_zone"], item["subnet_id"]))

    return {
        "region": region,
        "vpc": {
            "vpc_id": str(vpc.get("VpcId") or ""),
            "cidr_block": str(vpc.get("CidrBlock") or ""),
            "additional_cidr_blocks": [
                str(association.get("CidrBlock") or "")
                for association in vpc.get("CidrBlockAssociationSet") or []
                if str(association.get("CidrBlock") or "") != str(vpc.get("CidrBlock") or "")
            ],
            "name": _tag(vpc, "Name"),
            "dns_support": _vpc_attribute(client, vpc_id, "enableDnsSupport"),
            "dns_hostnames": _vpc_attribute(client, vpc_id, "enableDnsHostnames"),
        },
        "subnets": classified,
        "availability_zones": sorted({item["availability_zone"] for item in classified}),
        "vpc_endpoints": coverage,
        "nat_gateways": [
            {"id": str(gateway.get("NatGatewayId") or ""),
             "subnet_id": str(gateway.get("SubnetId") or ""),
             "state": str(gateway.get("State") or ""),
             "connectivity": str(gateway.get("ConnectivityType") or "public")}
            for gateway in nat_gateways
        ],
        "internet_gateways": [str(gateway.get("InternetGatewayId") or "")
                              for gateway in gateways],
        "proposal": {
            "alb_scheme": "internal",
            "alb_subnet_ids": propose_subnets(classified, "suitable_for_internal_alb"),
            "task_subnet_ids": propose_subnets(classified, "suitable_for_fargate_tasks"),
            # El origen real de los usuarios no se deduce de la topología: no se
            # propone ningún CIDR de entrada.
            "alb_ingress_cidrs": [],
            "alb_ingress_status": "pending-network-team",
            "missing_vpc_endpoints": sorted(service for service, item in coverage.items()
                                            if not item["present"]),
        },
    }


def _client(settings: Settings):
    import boto3

    if not settings.aws_region:
        raise ConfigurationError("MSR_AWS_REGION is mandatory for the discovery.")
    kwargs: dict = {"region_name": settings.aws_region}
    if settings.aws_profile:
        kwargs["profile_name"] = settings.aws_profile
    return boto3.Session(**kwargs).client("ec2")


def render_markdown(report: dict) -> str:
    vpc = report["vpc"]
    lines = [
        f"# Network discovery (read-only) — {vpc['vpc_id']} / {report['region']}",
        "",
        f"- CIDR: `{vpc['cidr_block']}`"
        + (f" (+ {', '.join(vpc['additional_cidr_blocks'])})"
           if vpc["additional_cidr_blocks"] else ""),
        f"- DNS support: `{vpc['dns_support']}` · DNS hostnames: `{vpc['dns_hostnames']}`",
        f"- Internet Gateways: {', '.join(report['internet_gateways']) or 'none'}",
        "- NAT Gateways: "
        + (", ".join(f"{gateway['id']} ({gateway['state']}, {gateway['subnet_id']})"
                     for gateway in report["nat_gateways"]) or "none"),
        "",
        "| Subnet | AZ | CIDR | Free IPs | Route table | Default egress | Internal ALB | Fargate |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for subnet in report["subnets"]:
        lines.append(
            f"| `{subnet['subnet_id']}` | {subnet['availability_zone']} | "
            f"`{subnet['cidr_block']}` | {subnet['available_ip_count']} | "
            f"`{subnet['routing']['route_table_id']}` | {subnet['routing']['egress']} | "
            f"{'yes' if subnet['suitable_for_internal_alb'] else 'no'} | "
            f"{'yes' if subnet['suitable_for_fargate_tasks'] else 'no'} |"
        )
    lines += ["", "## VPC endpoints", "",
              "| Service | Present | IDs |", "|---|---|---|"]
    for service, item in report["vpc_endpoints"].items():
        lines.append(f"| `{service}` | {'yes' if item['present'] else 'no'} | "
                     f"{', '.join(item['ids']) or '—'} |")
    proposal = report["proposal"]
    lines += [
        "",
        "## Proposal",
        "",
        f"- ALB scheme: `{proposal['alb_scheme']}`",
        f"- ALB subnets: {', '.join(proposal['alb_subnet_ids']) or 'none suitable'}",
        f"- Task subnets: {', '.join(proposal['task_subnet_ids']) or 'none suitable'}",
        f"- Ingress source: {proposal['alb_ingress_status']} "
        "(the corporate range cannot be inferred from the topology)",
        f"- Missing endpoints: {', '.join(proposal['missing_vpc_endpoints']) or 'none'}",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only network discovery before the apply.")
    parser.add_argument("--vpc-id", required=True, help="MSR lab VPC.")
    parser.add_argument("--json", action="store_true", help="JSON output.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        settings = get_settings()
        report = discover(_client(settings), args.vpc_id, settings.aws_region)
    except ConfigurationError as exc:
        print(json.dumps({"code": exc.code, "message": str(exc)},
                         ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json
          else render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
