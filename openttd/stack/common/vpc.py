from aws_cdk.core import (
    Construct,
    Fn,
    Stack,
    Tag,
)
from aws_cdk.aws_ec2 import (
    CfnInternetGateway,
    CfnSubnet,
    CfnVPCCidrBlock,
    InstanceType,
    IVpc,
    NatProvider,
    RouterType,
    Vpc,
)


class VpcStack(Stack):
    def __init__(self,
                 scope: Construct,
                 id: str,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Stack", "Common-Vpc")

        # TODO -- Add network security (ACL, etc)

        # NAT Gateways are very expensive; instead, run our own NAT Instance.
        # The only production traffic going through it, is the UDP traffic
        # of the Master Server (to query servers). All other traffic is done
        # via Application / Network Load Balancing.
        # Of course this will also be used to fetch container images, OS
        # updates, etc. But this traffic is rare and few apart.
        nat_provider = NatProvider.instance(
            instance_type=InstanceType("t3a.nano")
        )

        self._vpc = Vpc(self, "Vpc",
            max_azs=2,
            nat_gateway_provider=nat_provider,
        )

        # IPv6 is currently not supported by CDK.
        # This is done manually now, based on:
        # https://gist.github.com/milesjordan/d86942718f8d4dc20f9f331913e7367a

        ipv6_block = CfnVPCCidrBlock(self, "Ipv6",
            vpc_id=self._vpc.vpc_id,
            amazon_provided_ipv6_cidr_block=True,
        )

        # We need to sniff out the InternetGateway the VPC is using, as we
        # need to assign this for IPv6 routing too.
        for child in self._vpc.node.children:
            if isinstance(child, CfnInternetGateway):
                internet_gateway = child
                break
        else:
            raise Exception("Couldn't find the InternetGateway of the VPC")

        for index, subnet in enumerate(self._vpc.public_subnets):
            subnet.add_route("DefaultIpv6Route",
                router_id=internet_gateway.ref,
                router_type=RouterType.GATEWAY,
                destination_ipv6_cidr_block="::/0",
            )

            # This is of course not the best way to do this, but it seems CDK
            # currently allows no other way to set the IPv6 CIDR on subnets.
            assert isinstance(subnet.node.children[0], CfnSubnet)
            # As IPv6 are allocated on provisioning, we need to use "Fn::Cidr"
            # to get a subnet out of it.
            subnet.node.children[0].ipv6_cidr_block = Fn.select(
                index,
                Fn.cidr(
                    Fn.select(
                        0,
                        self._vpc.vpc_ipv6_cidr_blocks
                    ),
                    len(self._vpc.public_subnets),
                    "64"
                )
            )
            # Make sure the dependencies are correct, otherwise we might be
            # creating a subnet before IPv6 is added.
            subnet.node.add_dependency(ipv6_block)

    @property
    def vpc(self) -> IVpc:
        return self._vpc
