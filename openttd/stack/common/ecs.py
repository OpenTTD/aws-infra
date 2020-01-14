from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
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
)


class EcsStack(Stack):
    def __init__(self,
                 scope: Construct,
                 id: str,
                 vpc: IVpc,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Stack", "Common-Ecs")

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

    @property
    def cluster(self) -> ICluster:
        return self._cluster
