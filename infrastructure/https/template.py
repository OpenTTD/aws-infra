from aws_cdk.core import (
    CfnOutput,
    Construct,
    Stack,
    StringConcat,
    Tag,
    Token,
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
from aws_cdk.aws_ssm import StringParameter

from infrastructure.core.core import CoreStack
from infrastructure.core.listener_https import ListenerHTTPSStack
from infrastructure.core.parameter_store import ParameterStoreStack


class HTTPSTemplateStack(Stack):
    """Template stack that will serve an HTTP container via the HTTPS listener."""

    default = False  # type: bool
    subdomain_name = None  # type: str
    name = None  # type: str
    image = None  # type: str
    port = None  # type: int
    memory_limit_mib = None  # type: int

    def __init__(self, scope: Construct, id: str, core: CoreStack, listener_https: ListenerHTTPSStack, parameter_store: ParameterStoreStack, is_staging: bool, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        if is_staging:
            cluster = "Staging"
            desired_count = 1
        else:
            cluster = "Production"
            desired_count = 2

        name = f"{cluster}-{self.name}"

        Tag.add(self, "Stack", "HTTPSTemplate")
        Tag.add(self, "Application", self.name)
        Tag.add(self, "Cluster", cluster)

        task_definition = Ec2TaskDefinition(self, "TaskDef",
            network_mode=NetworkMode.BRIDGE,
        )

        log_group = LogGroup(self, "LogGroup")

        parameter_store.add_parameter(name, default="1")
        tag = Token.as_string(StringParameter.value_for_string_parameter(self, name))
        image = StringConcat().join(f"{self.image}:", tag)

        container = task_definition.add_container("Container",
            image=ContainerImage.from_registry(image),
            memory_limit_mib=self.memory_limit_mib,
#            readonly_root_filesystem=True,
            logging=LogDrivers.aws_logs(stream_prefix=name, log_group=log_group),
        )

        container.add_port_mappings(PortMapping(
            container_port=self.port,
            protocol=Protocol.TCP,
        ))

        service = Ec2Service(self, "Service",
            cluster=core.cluster,
            task_definition=task_definition,
            desired_count=desired_count,
        )

        service.add_placement_strategies(
            PlacementStrategy.spread_across(BuiltInAttributes.AVAILABILITY_ZONE),
        )

        if self.default:
            listener_https.add_default_target(
                port=self.port,
                service=service,
            )
        else:
            listener_https.add_targets(self.subdomain_name,
                port=self.port,
                service=service,
            )
