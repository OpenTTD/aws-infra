from aws_cdk.core import (
    CfnOutput,
    Construct,
    Stack,
)
from aws_cdk.aws_ecs import (
    BuiltInAttributes,
    ContainerImage,
    Ec2Service,
    Ec2TaskDefinition,
    LogDrivers,
    NetworkMode,
    PortMapping,
    PlacementStrategy,
    Protocol,
)
from aws_cdk.aws_logs import LogGroup

from infrastructure.core.core import CoreStack
from infrastructure.core.https_listener import HTTPSListenerStack


class HTTPSTemplateStack(Stack):
    """Template stack that will serve an HTTP container via the HTTPS listener."""

    default = False  # type: bool
    subdomain_name = None  # type: str
    name = None  # type: str
    image = None  # type: str
    port = None  # type: int
    memory_limit_mib = None  # type: int

    def __init__(self, scope: Construct, id: str, core: CoreStack, https_listener: HTTPSListenerStack, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        task_definition = Ec2TaskDefinition(self, "TaskDef",
            network_mode=NetworkMode.BRIDGE,
        )

        log_group = LogGroup(self, "LogGroup")

        container = task_definition.add_container("Container",
            image=ContainerImage.from_registry(self.image),
            memory_limit_mib=self.memory_limit_mib,
#            readonly_root_filesystem=True,
            logging=LogDrivers.aws_logs(stream_prefix=self.name, log_group=log_group),
        )

        container.add_port_mappings(PortMapping(
            container_port=self.port,
            protocol=Protocol.TCP,
        ))

        service = Ec2Service(self, "Service",
            cluster=core.cluster,
            task_definition=task_definition,
            desired_count=2,
        )

        service.add_placement_strategies(
            PlacementStrategy.spread_across(BuiltInAttributes.AVAILABILITY_ZONE),
        )

        if self.default:
            https_listener.add_default_target(
                port=self.port,
                service=service,
            )
        else:
            https_listener.add_targets(self.subdomain_name,
                port=self.port,
                service=service,
            )
