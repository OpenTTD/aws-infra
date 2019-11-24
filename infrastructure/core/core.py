from aws_cdk.core import (
    Construct,
    Stack,
)
from aws_cdk.aws_autoscaling import AutoScalingGroup
from aws_cdk.aws_ec2 import (
    InstanceType,
    IVpc,
    NatProvider,
    Vpc,
)
from aws_cdk.aws_elasticloadbalancingv2 import (
    ApplicationLoadBalancer,
    IApplicationLoadBalancer,
    IpAddressType,
)
from aws_cdk.aws_ecs import (
    Cluster,
    EcsOptimizedImage,
    ICluster,
)


class CoreStack(Stack):
    vpc = None  # type: IVpc
    alb = None  # type: IApplicationLoadBalancer
    cluster = None  # type: ICluster

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # NAT Gateways are very expensive; instead, run our own NAT Instance.
        # The only production traffic going through it, is the UDP traffic
        # of the Master Server (to query servers). All other traffic is done
        # via Application / Network Load Balancing.
        # Of course this will also be used to fetch container images, OS
        # updates, etc. But this traffic is rare and few apart.
        nat_provider = NatProvider.instance(
            instance_type=InstanceType("t3a.nano")
        )

        self.vpc = Vpc(self, "VPC",
            max_azs=2,
            nat_gateway_provider=nat_provider,
        )

        self.alb = ApplicationLoadBalancer(self, "ALB",
            vpc=self.vpc,
            internet_facing=True,
#            ip_address_type=IpAddressType.DUAL_STACK,
        )

        self.cluster = Cluster(self, "Cluster",
            vpc=self.vpc,
        )

        asg = AutoScalingGroup(self, "ClusterASG",
            vpc=self.vpc,
            instance_type=InstanceType("t3a.small"),
            machine_image=EcsOptimizedImage.amazon_linux2(),
            desired_capacity=2,
        )
        self.cluster.add_auto_scaling_group(asg)

        # TODO -- Add an IPv6 range to the VPC
        # TODO -- Add an IPv6 range to all the subnets
        # TODO -- Add an egress-only gateway (IPv6 only)
        # This currently cannot be done via CDK; suggested solutions:
        #  https://gist.github.com/milesjordan/d86942718f8d4dc20f9f331913e7367a
        #  https://docs.aws.amazon.com/cdk/latest/guide/cfn_layer.html

        # TODO -- Create VM to route all IPv6 traffic to NLB (NLB doesn't
        # support IPv6). This should add PROXY protocol to still allow finding
        # the original IPv6. nginx currently is the only one supporting this
        # with UDP and TCP, but only supports PROXY protocol v1.
        # This means that if we enable PROXY protocol on the NLB for IPv4,
        # all applications get a mix of v1/v2, depending on the source.
