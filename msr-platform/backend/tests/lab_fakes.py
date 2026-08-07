"""Dobles de sólo lectura de EC2, Systems Manager y Auto Scaling.

Reproducen el laboratorio de la PoC (una instancia en un ASG 1/1/1, etiquetada
por tags y con inventario de kernel) sin usar boto3 ni tocar AWS. Los tests
mutan el mundo (`FakeLabWorld`) para provocar cada escenario: parcheada,
vulnerable, SSM caído, cero instancias, instancias duplicadas, etc.
"""
from __future__ import annotations

import itertools

from fakes import EXECUTION_REFERENCE, FakeAwsProvider

from app.providers.base import (
    RESTORE_KIND_RESET_LAB,
    ExecutionStatus,
    PatchExecution,
    PatchRequest,
    RestoreExecution,
    RestoreRequest,
)

ACCOUNT_ID = "123456789012"
REGION = "eu-west-1"
ASG_NAME = "msr-poc-linux-patching-01-asg"
VULNERABLE_KERNEL = ("6.1.147", "180.264.amzn2023")
FIXED_KERNEL = ("6.1.176", "220.358.amzn2023")
ADVISORY = "ALAS2023-2026-1924"


class FakeLabInstance:
    """Instancia del laboratorio con todo su estado observable."""

    def __init__(self, instance_id: str, logical_lab_id: str, *, state: str = "running",
                 patched: bool = False, ping: str = "Online", asg_name: str = ASG_NAME,
                 lifecycle: str = "InService", asg_health: str = "Healthy",
                 ec2_ok: bool = True, tags: dict | None = None):
        version, release = FIXED_KERNEL if patched else VULNERABLE_KERNEL
        self.instance_id = instance_id
        self.state = state
        self.ping = ping
        self.asg_name = asg_name
        self.lifecycle = lifecycle
        self.asg_health = asg_health
        self.ec2_ok = ec2_ok
        self.patched = patched
        self.kernel_version = version
        self.kernel_release = release
        self.scanned = True
        self.tags = tags if tags is not None else {
            "msr-poc": "true",
            "msr-lab-id": logical_lab_id,
            "msr-environment": "development",
            "msr-resettable": "true",
            "PatchGroup": "msr-poc-linux",
            "Name": f"msr-poc-{logical_lab_id}",
        }

    def patch(self) -> None:
        self.patched = True
        self.kernel_version, self.kernel_release = FIXED_KERNEL


class FakeLabWorld:
    """Conjunto de instancias visibles para los dobles de AWS."""

    def __init__(self, logical_lab_id: str, instances: list[FakeLabInstance] | None = None):
        self.logical_lab_id = logical_lab_id
        self.instances: list[FakeLabInstance] = (
            instances if instances is not None
            else [FakeLabInstance("i-0aaaaaaaaaaaaaaa1", logical_lab_id)])
        self._ids = itertools.count(2)

    def add(self, **kwargs) -> FakeLabInstance:
        instance = FakeLabInstance(f"i-0aaaaaaaaaaaaaaa{next(self._ids)}",
                                  self.logical_lab_id, **kwargs)
        self.instances.append(instance)
        return instance

    def get(self, instance_id: str) -> FakeLabInstance | None:
        return next((i for i in self.instances if i.instance_id == instance_id), None)

    def replace(self, instance_id: str, **kwargs) -> FakeLabInstance:
        """Sustituye la instancia como lo haría el ASG tras un reset."""
        self.instances = [i for i in self.instances if i.instance_id != instance_id]
        return self.add(**kwargs)


class FakeEc2:
    def __init__(self, world: FakeLabWorld):
        self.world = world

    def describe_instances(self, Filters=None) -> dict:  # noqa: N803 (API de boto3)
        states: list[str] | None = None
        required: dict[str, str] = {}
        for item in Filters or []:
            if item["Name"] == "instance-state-name":
                states = list(item["Values"])
            elif item["Name"].startswith("tag:"):
                required[item["Name"][4:]] = item["Values"][0]
        matched = [
            instance for instance in self.world.instances
            if (states is None or instance.state in states)
            and all(instance.tags.get(key) == value for key, value in required.items())]
        return {"Reservations": [{"OwnerId": ACCOUNT_ID, "Instances": [
            {
                "InstanceId": instance.instance_id,
                "State": {"Name": instance.state},
                "ImageId": "ami-0lab",
                "Placement": {"AvailabilityZone": f"{REGION}a"},
                "PlatformDetails": "Linux/UNIX",
                "Tags": [{"Key": k, "Value": v} for k, v in instance.tags.items()],
            } for instance in matched]}]}

    def describe_instance_status(self, InstanceIds=None) -> dict:  # noqa: N803
        instance = self.world.get((InstanceIds or [""])[0])
        if instance is None:
            return {"InstanceStatuses": []}
        status = "ok" if instance.ec2_ok else "impaired"
        return {"InstanceStatuses": [{"InstanceId": instance.instance_id,
                                      "InstanceStatus": {"Status": status},
                                      "SystemStatus": {"Status": status}}]}


class FakeSsm:
    def __init__(self, world: FakeLabWorld):
        self.world = world

    def describe_instance_information(self, Filters=None) -> dict:  # noqa: N803
        wanted = (Filters or [{}])[0].get("Values") or []
        entries = [{"InstanceId": instance.instance_id, "PingStatus": instance.ping}
                   for instance in self.world.instances
                   if instance.instance_id in wanted and instance.ping]
        return {"InstanceInformationList": entries}

    def list_inventory_entries(self, InstanceId=None, TypeName=None,  # noqa: N803
                               Filters=None) -> dict:
        instance = self.world.get(InstanceId or "")
        if instance is None:
            return {"Entries": []}
        return {"Entries": [{"Name": "kernel", "Version": instance.kernel_version,
                             "Release": instance.kernel_release, "Architecture": "x86_64"}]}

    def describe_instance_patches(self, InstanceId=None, Filters=None) -> dict:  # noqa: N803
        instance = self.world.get(InstanceId or "")
        if instance is None or instance.patched:
            return {"Patches": []}
        return {"Patches": [{"Title": f"kernel {ADVISORY}", "KBId": ADVISORY,
                             "State": "Missing"}]}

    def describe_instance_patch_states(self, InstanceIds=None) -> dict:  # noqa: N803
        instance = self.world.get((InstanceIds or [""])[0])
        if instance is None or not instance.scanned:
            return {"InstancePatchStates": []}
        return {"InstancePatchStates": [{"InstanceId": instance.instance_id,
                                         "Operation": "Scan",
                                         "OperationEndTime": "2026-08-05T00:00:00Z"}]}


class FakeAutoscaling:
    def __init__(self, world: FakeLabWorld):
        self.world = world

    def describe_auto_scaling_instances(self, InstanceIds=None) -> dict:  # noqa: N803
        instance = self.world.get((InstanceIds or [""])[0])
        if instance is None or not instance.asg_name:
            return {"AutoScalingInstances": []}
        return {"AutoScalingInstances": [{
            "InstanceId": instance.instance_id,
            "AutoScalingGroupName": instance.asg_name,
            "LifecycleState": instance.lifecycle,
            "HealthStatus": instance.asg_health}]}

    def describe_auto_scaling_groups(self, AutoScalingGroupNames=None) -> dict:  # noqa: N803
        members = [i for i in self.world.instances if i.asg_name in (AutoScalingGroupNames or [])]
        return {"AutoScalingGroups": [{
            "AutoScalingGroupName": (AutoScalingGroupNames or [ASG_NAME])[0],
            "DesiredCapacity": 1, "MinSize": 1, "MaxSize": 1,
            "Instances": [{"InstanceId": i.instance_id, "LifecycleState": i.lifecycle,
                           "HealthStatus": i.asg_health} for i in members]}]}


class FakeConditionalCheckFailed(Exception):
    """Misma clase de error que botocore para una condición no satisfecha."""


FakeConditionalCheckFailed.__name__ = "ConditionalCheckFailedException"


class FakeDynamoDb:
    """Tabla de locks en memoria con la semántica condicional de DynamoDB.

    Sólo implementa las tres operaciones que usa el lock y evalúa las mismas
    condiciones: ítem inexistente, ítem caducado o mismo dueño para tomarlo, y
    dueño coincidente para liberarlo. El TTL asíncrono de DynamoDB no se
    simula a propósito: el lock no puede depender de él.
    """

    def __init__(self):
        self.items: dict[str, dict] = {}
        self.tables: list[str] = []
        self.failure: Exception | None = None

    def _guard(self) -> None:
        if self.failure is not None:
            raise self.failure

    def put_item(self, TableName, Item, ConditionExpression="",  # noqa: N803
                 ExpressionAttributeValues=None) -> dict:  # noqa: N803
        self._guard()
        self.tables.append(TableName)
        key = Item["lab_id"]["S"]
        values = ExpressionAttributeValues or {}
        current = self.items.get(key)
        if current is not None and ConditionExpression:
            now = int(values[":now"]["N"])
            expired = int(current["expires_at"]["N"]) <= now
            same_owner = current["owner"]["S"] == values[":owner"]["S"]
            if not (expired or same_owner):
                raise FakeConditionalCheckFailed(key)
        self.items[key] = dict(Item)
        return {}

    def delete_item(self, TableName, Key, ConditionExpression="",  # noqa: N803
                    ExpressionAttributeValues=None) -> dict:  # noqa: N803
        self._guard()
        key = Key["lab_id"]["S"]
        values = ExpressionAttributeValues or {}
        current = self.items.get(key)
        if current is None or current["owner"]["S"] != values[":owner"]["S"]:
            raise FakeConditionalCheckFailed(key)
        del self.items[key]
        return {}

    def get_item(self, TableName, Key, ConsistentRead=False) -> dict:  # noqa: N803
        self._guard()
        item = self.items.get(Key["lab_id"]["S"])
        return {"Item": dict(item)} if item is not None else {}


class FakeLabAwsProvider(FakeAwsProvider):
    """Provider AWS falso con los clientes de sólo lectura del laboratorio.

    El reset simulado sustituye la instancia del mundo por otra vulnerable, como
    haría `MSR-ResetLabInstance` a través del Auto Scaling Group.
    """

    def __init__(self, world: FakeLabWorld, *, reset_status=ExecutionStatus.SUCCEEDED,
                 replaces: bool = True, replacement_patched: bool = False,
                 replacement_ping: str = "Online", **kwargs):
        super().__init__(**kwargs)
        self.world = world
        self.ec2 = FakeEc2(world)
        self.ssm = FakeSsm(world)
        self.autoscaling = FakeAutoscaling(world)
        self.dynamodb = FakeDynamoDb()
        self.reset_status = reset_status
        self.replaces = replaces
        self.replacement_patched = replacement_patched
        self.replacement_ping = replacement_ping
        self.started_runbooks: list[str] = []
        self.reset_requests: list[object] = []

    @staticmethod
    def _is_reset(request: PatchRequest | RestoreRequest | None) -> bool:
        return (isinstance(request, RestoreRequest)
                and request.restore_kind == RESTORE_KIND_RESET_LAB)

    def start(self, request: PatchRequest | RestoreRequest, idempotency_key: str):
        if self._is_reset(request):
            self.started_runbooks.append(RESTORE_KIND_RESET_LAB)
            self.reset_requests.append(request)
            if self.reset_status is ExecutionStatus.SUCCEEDED and self.replaces:
                previous = request.primary_target().instance_id or ""
                self.world.replace(previous, patched=self.replacement_patched,
                                   ping=self.replacement_ping)
            return RestoreExecution(provider=self.name, provider_reference=EXECUTION_REFERENCE,
                                    status=ExecutionStatus.RUNNING, dry_run=request.dry_run,
                                    raw_status="InProgress")
        self.started_runbooks.append("patch")
        return super().start(request, idempotency_key)

    def poll(self, provider_reference: str,
             request: PatchRequest | RestoreRequest | None = None):
        self.polls += 1
        if self._is_reset(request):
            new_id = self.world.instances[0].instance_id if self.world.instances else ""
            return RestoreExecution(
                provider=self.name, provider_reference=provider_reference,
                status=self.reset_status, dry_run=False,
                raw_status=self.reset_status.value,
                new_instance_id=new_id,
                report={"NewInstanceId": new_id, "VulnerableState": "VULNERABLE",
                        "HealthState": "HEALTHY", "Advisory": ADVISORY})
        return PatchExecution(provider=self.name, provider_reference=provider_reference,
                              status=self.poll_status, dry_run=False,
                              raw_status=self.poll_status.value)
