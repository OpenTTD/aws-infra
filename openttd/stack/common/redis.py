from aws_cdk.core import (
    Construct,
    Stack,
    Tags,
)
from aws_cdk.aws_ec2 import (
    IVpc,
    Port,
    SecurityGroup,
)
from aws_cdk.aws_elasticache import (
    CfnCacheCluster,
    CfnSubnetGroup,
)


class RedisStack(Stack):
    application_name = "Redis"
    subdomain_name = "redis"

    def __init__(self, scope: Construct, id: str, *, vpc: IVpc, ecs_source_security_group: SecurityGroup, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Stack", "Common-Redis")

        security_group = SecurityGroup(
            self,
            "SecurityGroup",
            vpc=vpc,
            allow_all_outbound=False,
        )
        security_group.add_ingress_rule(
            peer=ecs_source_security_group,
            connection=Port.tcp(6379),
            description="ECS to redis",
        )

        subnet_group = CfnSubnetGroup(
            self,
            "Subnet",
            description="Subnet",
            subnet_ids=[subnet.subnet_id for subnet in vpc.private_subnets],
        )

        self.redis = CfnCacheCluster(
            self,
            "Redis",
            cache_node_type="cache.t3.micro",
            engine="redis",
            num_cache_nodes=1,
            auto_minor_version_upgrade=True,
            cache_subnet_group_name=subnet_group.ref,
            cluster_name="redis",
            snapshot_retention_limit=1,
            engine_version="6.x",
            vpc_security_group_ids=[security_group.security_group_id],
        )
