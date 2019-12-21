from aws_cdk.core import (
    CfnOutput,
    Construct,
    Stack,
    StringConcat,
    Tag,
    Token,
)
from aws_cdk.aws_cloudformation import NestedStack
from aws_cdk.aws_ecs import (
    BuiltInAttributes,
    ContainerImage,
    Ec2Service,
    Ec2TaskDefinition,
    ICluster,
    LogDriver,
    LogDrivers,
    NetworkMode,
    PortMapping,
    PlacementStrategy,
    Protocol,
)

from aws_cdk.aws_ssm import StringParameter

from openttd.construct.image_from_parameter_store import ImageFromParameterStore
from openttd.stack.common import (
    listener_https,
    tasks,
)


class ECSHTTPSContainer(Construct):
    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 subdomain_name: str,
                 application_name: str,
                 image_name: str,
                 port: int,
                 memory_limit_mib: int,
                 desired_count: int,
                 cluster: ICluster) -> None:
        super().__init__(scope, id)

        log_group = tasks.add_logging(application_name)
        task_role = tasks.add_role(application_name)

        logging = LogDrivers.aws_logs(
            stream_prefix=application_name,
            log_group=log_group,
        )

        image = ImageFromParameterStore(self, "ImageName",
            parameter_name=application_name,
            image_name=image_name,
        )

        task_definition = Ec2TaskDefinition(self, "TaskDef",
            network_mode=NetworkMode.BRIDGE,
            execution_role=task_role,
            task_role=task_role,
        )

        container = task_definition.add_container("Container",
            image=ContainerImage.from_registry(image.image_ref),
            memory_limit_mib=memory_limit_mib,
#            readonly_root_filesystem=True,
            logging=logging,
        )

        container.add_port_mappings(PortMapping(
            container_port=port,
            protocol=Protocol.TCP,
        ))

        service = Ec2Service(self, "Service",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=desired_count,
        )

        service.add_placement_strategies(
            PlacementStrategy.spread_across(BuiltInAttributes.AVAILABILITY_ZONE),
        )

        listener_https.add_targets(
            subdomain_name=subdomain_name,
            port=port,
            service=service,
        )
