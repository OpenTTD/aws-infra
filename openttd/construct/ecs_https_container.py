from aws_cdk.core import Construct
from aws_cdk.aws_ecs import (
    BuiltInAttributes,
    ContainerImage,
    Ec2Service,
    Ec2TaskDefinition,
    ICluster,
    LogDrivers,
    NetworkMode,
    PortMapping,
    PlacementStrategy,
    Protocol,
    Secret,
)
from typing import Mapping

from openttd.construct.image_from_parameter_store import ImageFromParameterStore
from openttd.construct.policy import Policy
from openttd.enumeration import Deployment
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
                 deployment: Deployment,
                 policy: Policy,
                 application_name: str,
                 image_name: str,
                 port: int,
                 memory_limit_mib: int,
                 desired_count: int,
                 cluster: ICluster,
                 priority: int,
                 environment: Mapping[str, str] = {},
                 secrets: Mapping[str, Secret] = {}) -> None:
        super().__init__(scope, id)

        full_application_name = f"{deployment.value}-{application_name}"

        log_group = tasks.add_logging(full_application_name)
        task_role = tasks.add_role(full_application_name)
        policy.add_role(task_role)

        logging = LogDrivers.aws_logs(
            stream_prefix=full_application_name,
            log_group=log_group,
        )

        image = ImageFromParameterStore(self, "ImageName",
            parameter_name=f"/Version/{deployment.value}/{application_name}",
            image_name=image_name,
            policy=policy,
        )

        task_definition = Ec2TaskDefinition(self, "TaskDef",
            network_mode=NetworkMode.BRIDGE,
            execution_role=task_role,
            task_role=task_role,
        )

        container = task_definition.add_container("Container",
            image=ContainerImage.from_registry(image.image_ref),
            memory_limit_mib=memory_limit_mib,
            logging=logging,
            environment=environment,
            secrets=secrets,
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
        policy.add_service(service)

        service.add_placement_strategies(
            PlacementStrategy.spread_across(BuiltInAttributes.AVAILABILITY_ZONE),
        )

        listener_https.add_targets(
            subdomain_name=subdomain_name,
            port=port,
            service=service,
            priority=priority,
        )
