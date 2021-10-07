import re
import ipaddress
from enum import Enum
from pydantic.dataclasses import dataclass
from pydantic import ValidationError, validator
from argus.db.db_types import ArgusUDTBase


@dataclass(init=True, repr=True)
class CloudInstanceDetails(ArgusUDTBase):
    provider: str = ""
    region: str = ""
    ip: str = ""
    private_ip: str = ""

    @classmethod
    def from_db_udt(cls, udt):
        return cls(provider=udt.provider, region=udt.region, ip=udt.ip, private_ip=udt.private_ip)

    @validator("ip")
    def valid_ipv4_address(cls, v):
        try:
            ipaddress.ip_address(v)
        except ValueError:
            raise ValidationError(f"Not a valid IPv4(v6) address: {v}")

        return v

    @validator("private_ip")
    def valid_private_ipv4_address(cls, v):
        try:
            ipaddress.ip_address(v)
        except ValueError:
            raise ValidationError(f"Not a valid IPv4(v6) address: {v}")

        return v


@dataclass(init=True, repr=True)
class CloudNodesInfo(ArgusUDTBase):
    image_id: str
    instance_type: str
    node_amount: int
    post_behaviour: str

    @classmethod
    def from_db_udt(cls, udt):
        return cls(image_id=udt.image_id, instance_type=udt.instance_type,
                   node_amount=udt.node_amount, post_behaviour=udt.post_behaviour)


@dataclass(init=True, repr=True)
class BaseCloudSetupDetails(ArgusUDTBase):
    db_node: CloudNodesInfo
    loader_node: CloudNodesInfo
    monitor_node: CloudNodesInfo
    backend: str = None
    _typename = "CloudSetupDetails"

    @classmethod
    def from_db_udt(cls, udt):
        db_node = CloudNodesInfo(*udt.db_node)
        loader_node = CloudNodesInfo(*udt.loader_node)
        monitor_node = CloudNodesInfo(*udt.monitor_node)
        return cls(db_node=db_node, loader_node=loader_node, monitor_node=monitor_node)


@dataclass(init=True, repr=True)
class AWSSetupDetails(BaseCloudSetupDetails):
    backend: str = "aws"


@dataclass(init=True, repr=True)
class GCESetupDetails(BaseCloudSetupDetails):
    backend: str = "gce"


class ResourceState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    TERMINATED = "terminated"


@dataclass(init=True, repr=True)
class CloudResource(ArgusUDTBase):
    name: str
    resource_state: str
    instance_info: CloudInstanceDetails

    @property
    def state(self):
        return ResourceState(self.resource_state)

    @state.setter
    def state(self, value: ResourceState):
        self.resource_state = ResourceState(value).value

    @classmethod
    def from_db_udt(cls, udt):
        instance_info = CloudInstanceDetails.from_db_udt(udt.instance_info)
        return cls(name=udt.name, resource_state=udt.resource_state, instance_info=instance_info)
