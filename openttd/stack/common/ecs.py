from aws_cdk.core import (
    Construct,
    Stack,
    Tags,
)
from aws_cdk.aws_autoscaling import AutoScalingGroup
from aws_cdk.aws_ecs import (
    Cluster,
    EcsOptimizedImage,
    ICluster,
)
from aws_cdk.aws_ec2 import (
    InstanceType,
    IVpc,
    Port,
    SecurityGroup,
)


class EcsStack(Stack):
    def __init__(self,
                 scope: Construct,
                 id: str,
                 vpc: IVpc,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Stack", "Common-Ecs")

        self._cluster = Cluster(self, "Cluster",
            vpc=vpc,
        )

        asg = AutoScalingGroup(self, "ClusterASG",
            vpc=vpc,
            instance_type=InstanceType("t3a.small"),
            machine_image=EcsOptimizedImage.amazon_linux2(),
            min_capacity=2,
        )
        self._cluster.add_auto_scaling_group(asg)

        # Create a SecurityGroup that the NLB can use to allow traffic from
        # NLB to us. This avoids a cyclic dependency.
        self.security_group = SecurityGroup(self, "SecurityGroup",
            vpc=vpc,
            allow_all_outbound=False,
        )

        # We could also make an additional security-group and add that to
        # the ASG, but it keeps adding up. This makes it a tiny bit
        # easier to get an overview what traffic is allowed from the
        # console on AWS.
        asg.node.children[0].add_ingress_rule(
            peer=self.security_group,
            connection=Port.tcp_range(32768, 65535),
            description="NLB-self to target",
        )

    @property
    def cluster(self) -> ICluster:
        return self._cluster
