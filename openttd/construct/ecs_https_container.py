from aws_cdk.core import (
    Construct,
    Duration,
)
from aws_cdk.aws_ecs import (
    BuiltInAttributes,
    ContainerImage,
    Ec2Service,
    Ec2TaskDefinition,
    ICluster,
    LogDrivers,
    MountPoint,
    NetworkMode,
    PortMapping,
    PlacementStrategy,
    Protocol,
    Secret,
    Volume,
)
from aws_cdk.aws_elasticloadbalancingv2 import ApplicationTargetGroup
from typing import (
    List,
    Mapping,
    Optional,
)

from openttd.construct.image_from_parameter_store import ImageFromParameterStore
from openttd.construct.policy import Policy
from openttd.enumeration import Deployment
from openttd.stack.common import (
    listener_https,
    tasks,
)


class ECSHTTPSContainer(Construct):
    def __init__(
        self,
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
        path_pattern: Optional[str] = None,
        health_check_grace_period: Optional[Duration] = None,
        allow_via_http: Optional[bool] = False,
        no_dns: Optional[bool] = False,
        command: Optional[List[str]] = None,
        environment: Mapping[str, str] = {},
        secrets: Mapping[str, Secret] = {},
        volumes: Mapping[str, Volume] = {},
        target_group: Optional[ApplicationTargetGroup] = None,
        single_instance: bool = False,
    ) -> None:
        super().__init__(scope, id)

        full_application_name = f"{deployment.value}-{application_name}"

        log_group = tasks.add_logging(full_application_name)
        self.task_role = tasks.add_role(full_application_name)
        policy.add_role(self.task_role)

        logging = LogDrivers.aws_logs(
            stream_prefix=full_application_name,
            log_group=log_group,
        )

        image = ImageFromParameterStore(
            self,
            "ImageName",
            parameter_name=f"/Version/{deployment.value}/{application_name}",
            image_name=image_name,
            policy=policy,
        )

        task_definition = Ec2TaskDefinition(
            self,
            "TaskDef",
            network_mode=NetworkMode.BRIDGE,
            execution_role=self.task_role,
            task_role=self.task_role,
            volumes=list(volumes.values()),
        )

        self.container = task_definition.add_container(
            "Container",
            image=ContainerImage.from_registry(image.image_ref),
            memory_limit_mib=memory_limit_mib,
            logging=logging,
            environment=environment,
            secrets=secrets,
            command=command,
        )
        self.container.add_mount_points(
            *[
                MountPoint(
                    container_path=path,
                    read_only=False,
                    source_volume=volume.name,
                )
                for path, volume in volumes.items()
            ]
        )

        self.add_port(
            port=port,
        )

        max_healthy_percent = 200
        min_healthy_percent = 50
        if single_instance:
            max_healthy_percent = 100
            min_healthy_percent = 0

        self.service = Ec2Service(
            self,
            "Service",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=desired_count,
            health_check_grace_period=health_check_grace_period,
            max_healthy_percent=max_healthy_percent,
            min_healthy_percent=min_healthy_percent,
        )
        policy.add_service(self.service)
        policy.add_cluster(cluster)

        self.service.add_placement_strategies(
            PlacementStrategy.spread_across(BuiltInAttributes.AVAILABILITY_ZONE),
        )

        self.target_group = self.add_target(
            subdomain_name=subdomain_name,
            port=port,
            priority=priority,
            path_pattern=path_pattern,
            allow_via_http=allow_via_http,
            no_dns=no_dns,
            target_group=target_group,
        )

        # Remove the security group from this stack, and add it to the ALB stack
        self.service.node.try_remove_child("SecurityGroup1")
        for security_group in cluster.connections.security_groups:
            self.service.connections.add_security_group(security_group)

    def add_port(self, port: int):
        self.container.add_port_mappings(
            PortMapping(
                container_port=port,
                protocol=Protocol.TCP,
            )
        )

    def add_udp_port(self, port: int):
        self.container.add_port_mappings(
            PortMapping(
                container_port=port,
                protocol=Protocol.UDP,
            )
        )

    def add_target(
        self,
        subdomain_name: str,
        port: int,
        priority: int,
        *,
        path_pattern: Optional[str] = None,
        allow_via_http: Optional[bool] = False,
        no_dns: Optional[bool] = False,
        target_group: Optional[ApplicationTargetGroup] = None,
    ) -> ApplicationTargetGroup:
        return listener_https.add_targets(
            subdomain_name=subdomain_name,
            port=port,
            target=self.service.load_balancer_target(container_name="Container", container_port=port),
            priority=priority,
            path_pattern=path_pattern,
            allow_via_http=allow_via_http,
            no_dns=no_dns,
            target_group=target_group,
        )
