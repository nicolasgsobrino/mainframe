"""Descubrimiento de red: clasificación de subnets y propuesta de topología.

Ningún test contacta con AWS: el cliente EC2 es un doble que sólo responde a
`Describe*`, y cualquier otra llamada hace fallar el test.
"""
from __future__ import annotations

import pytest

from app.config import ConfigurationError
from app.net_discovery import (
    REQUIRED_ENDPOINT_SERVICES,
    classify_subnet,
    discover,
    endpoint_coverage,
    propose_subnets,
    render_markdown,
    route_target,
    subnet_routing,
)

REGION = "eu-north-1"
VPC_ID = "vpc-023864c0ca3c82eab"

PRIVATE_TABLE = {
    "RouteTableId": "rtb-private",
    "Associations": [{"SubnetId": "subnet-private-a"}, {"SubnetId": "subnet-private-b"}],
    "Routes": [
        {"DestinationCidrBlock": "10.0.0.0/16", "GatewayId": "local", "State": "active"},
        {"DestinationCidrBlock": "0.0.0.0/0", "NatGatewayId": "nat-1", "State": "active"},
    ],
}
PUBLIC_TABLE = {
    "RouteTableId": "rtb-public",
    "Associations": [{"SubnetId": "subnet-public-a"}],
    "Routes": [
        {"DestinationCidrBlock": "10.0.0.0/16", "GatewayId": "local", "State": "active"},
        {"DestinationCidrBlock": "0.0.0.0/0", "GatewayId": "igw-1", "State": "active"},
    ],
}
ISOLATED_TABLE = {
    "RouteTableId": "rtb-main",
    "Associations": [{"Main": True}],
    "Routes": [
        {"DestinationCidrBlock": "10.0.0.0/16", "GatewayId": "local", "State": "active"},
    ],
}

ROUTE_TABLES = [PRIVATE_TABLE, PUBLIC_TABLE, ISOLATED_TABLE]

SUBNETS = [
    {"SubnetId": "subnet-private-a", "AvailabilityZone": f"{REGION}a",
     "CidrBlock": "10.0.1.0/24", "AvailableIpAddressCount": 250,
     "MapPublicIpOnLaunch": False, "Tags": [{"Key": "Name", "Value": "lab-a"}]},
    {"SubnetId": "subnet-private-b", "AvailabilityZone": f"{REGION}b",
     "CidrBlock": "10.0.2.0/24", "AvailableIpAddressCount": 250,
     "MapPublicIpOnLaunch": False, "Tags": []},
    {"SubnetId": "subnet-public-a", "AvailabilityZone": f"{REGION}a",
     "CidrBlock": "10.0.3.0/24", "AvailableIpAddressCount": 250,
     "MapPublicIpOnLaunch": True, "Tags": []},
    {"SubnetId": "subnet-isolated-c", "AvailabilityZone": f"{REGION}c",
     "CidrBlock": "10.0.4.0/28", "AvailableIpAddressCount": 3,
     "MapPublicIpOnLaunch": False, "Tags": []},
]


class FakeEc2:
    """Cliente EC2 de sólo lectura: cualquier operación mutativa es un error."""

    def __init__(self, *, subnets=None, endpoints=None, nat_gateways=None,
                 internet_gateways=None, vpcs=None):
        self.pages = {
            "describe_vpcs": ("Vpcs", vpcs if vpcs is not None else [{
                "VpcId": VPC_ID, "CidrBlock": "10.0.0.0/16",
                "CidrBlockAssociationSet": [{"CidrBlock": "10.0.0.0/16"}],
                "Tags": [{"Key": "Name", "Value": "corp-vpc"}],
            }]),
            "describe_subnets": ("Subnets", SUBNETS if subnets is None else subnets),
            "describe_route_tables": ("RouteTables", ROUTE_TABLES),
            "describe_vpc_endpoints": ("VpcEndpoints", endpoints or []),
            "describe_nat_gateways": ("NatGateways", nat_gateways if nat_gateways is not None
                                      else [{"NatGatewayId": "nat-1", "SubnetId": "subnet-public-a",
                                             "State": "available", "ConnectivityType": "public"}]),
            "describe_internet_gateways": ("InternetGateways",
                                           internet_gateways if internet_gateways is not None
                                           else [{"InternetGatewayId": "igw-1"}]),
        }
        self.calls: list[str] = []

    def get_paginator(self, operation: str):
        key, items = self.pages[operation]
        self.calls.append(operation)

        class Paginator:
            def paginate(self, **kwargs):
                return [{key: items}]

        return Paginator()

    def describe_vpc_attribute(self, VpcId: str, Attribute: str):  # noqa: N803 - API de boto3
        self.calls.append(f"describe_vpc_attribute:{Attribute}")
        return {Attribute[0].upper() + Attribute[1:]: {"Value": True}}

    def __getattr__(self, name: str):
        raise AssertionError(f"El descubrimiento no puede llamar a {name}.")


def test_the_route_target_is_classified_by_its_gateway_kind():
    assert route_target({"GatewayId": "igw-1"})["kind"] == "internet-gateway"
    assert route_target({"GatewayId": "local"})["kind"] == "local"
    assert route_target({"GatewayId": "vgw-1"})["kind"] == "virtual-private-gateway"
    assert route_target({"NatGatewayId": "nat-1"})["kind"] == "nat-gateway"
    assert route_target({"TransitGatewayId": "tgw-1"})["kind"] == "transit-gateway"


def test_a_subnet_without_its_own_table_falls_back_to_the_main_table():
    routing = subnet_routing("subnet-isolated-c", ROUTE_TABLES)

    assert routing["route_table_id"] == "rtb-main"
    assert routing["is_main_table"] is True
    assert routing["egress"] == "none"


def test_the_private_subnets_route_to_the_nat_gateway():
    routing = subnet_routing("subnet-private-a", ROUTE_TABLES)

    assert routing["egress"] == "nat-gateway"
    assert routing["default_route_target"] == "nat-1"


def test_a_public_subnet_is_not_proposed_for_an_internal_alb():
    coverage = endpoint_coverage([], REGION)
    public = classify_subnet(SUBNETS[2], subnet_routing("subnet-public-a", ROUTE_TABLES),
                             coverage)

    assert public["is_public"] is True
    assert public["suitable_for_internal_alb"] is False
    assert any("Internet Gateway" in reason for reason in public["alb_blockers"])


def test_a_subnet_without_egress_or_endpoints_cannot_host_the_tasks():
    coverage = endpoint_coverage([], REGION)
    isolated = classify_subnet(SUBNETS[3], subnet_routing("subnet-isolated-c", ROUTE_TABLES),
                               coverage)

    assert isolated["suitable_for_fargate_tasks"] is False
    assert any("VPC endpoints" in reason for reason in isolated["task_blockers"])
    # Y tampoco tiene IPs para el ALB.
    assert isolated["suitable_for_internal_alb"] is False


def test_complete_vpc_endpoints_replace_the_nat_egress():
    endpoints = [{"VpcEndpointId": f"vpce-{index}", "VpcEndpointType": "Interface",
                  "State": "available", "SubnetIds": ["subnet-isolated-c"],
                  "ServiceName": f"com.amazonaws.{REGION}.{service}"}
                 for index, service in enumerate(REQUIRED_ENDPOINT_SERVICES)]
    coverage = endpoint_coverage(endpoints, REGION)
    subnet = dict(SUBNETS[3], AvailableIpAddressCount=250)
    isolated = classify_subnet(subnet, subnet_routing("subnet-isolated-c", ROUTE_TABLES),
                               coverage)

    assert all(item["present"] for item in coverage.values())
    assert isolated["suitable_for_fargate_tasks"] is True


def test_the_proposal_picks_one_subnet_per_availability_zone():
    report = discover(FakeEc2(), VPC_ID, REGION)

    assert report["proposal"]["alb_subnet_ids"] == ["subnet-private-a", "subnet-private-b"]
    assert len({subnet["subnet_id"] for subnet in report["subnets"]}) == len(SUBNETS)
    # Dos zonas distintas: requisito del ALB.
    zones = {subnet["availability_zone"] for subnet in report["subnets"]
             if subnet["subnet_id"] in report["proposal"]["alb_subnet_ids"]}
    assert len(zones) == 2


def test_the_proposal_never_invents_an_ingress_cidr():
    report = discover(FakeEc2(), VPC_ID, REGION)

    assert report["proposal"]["alb_ingress_cidrs"] == []
    assert report["proposal"]["alb_ingress_status"] == "pending-network-team"
    # El CIDR de la VPC no se usa como sucedáneo del origen corporativo.
    assert report["vpc"]["cidr_block"] not in str(report["proposal"])
    assert report["proposal"]["alb_scheme"] == "internal"


def test_the_proposal_is_empty_when_no_subnet_qualifies():
    only_public = [SUBNETS[2]]

    report = discover(FakeEc2(subnets=only_public), VPC_ID, REGION)

    assert report["proposal"]["alb_subnet_ids"] == []
    assert propose_subnets(report["subnets"], "suitable_for_internal_alb") == []


def test_the_report_lists_the_missing_endpoints_and_the_existing_gateways():
    report = discover(FakeEc2(), VPC_ID, REGION)

    assert report["proposal"]["missing_vpc_endpoints"] == sorted(REQUIRED_ENDPOINT_SERVICES)
    assert report["internet_gateways"] == ["igw-1"]
    assert report["nat_gateways"][0]["id"] == "nat-1"
    assert report["vpc"]["dns_support"] is True and report["vpc"]["dns_hostnames"] is True


def test_an_unknown_vpc_stops_the_discovery():
    with pytest.raises(ConfigurationError):
        discover(FakeEc2(vpcs=[]), VPC_ID, REGION)


def test_the_discovery_only_issues_read_only_calls():
    client = FakeEc2()

    discover(client, VPC_ID, REGION)

    assert client.calls
    assert all(call.startswith("describe_") for call in client.calls)


def test_the_markdown_report_shows_the_topology_and_the_pending_dependency():
    report = discover(FakeEc2(), VPC_ID, REGION)

    markdown = render_markdown(report)

    assert VPC_ID in markdown
    assert "subnet-private-a" in markdown
    assert "pending-network-team" in markdown
    assert "0.0.0.0/0" not in markdown
