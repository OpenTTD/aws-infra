from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
)
from aws_cdk.aws_ec2 import IVpc
from aws_cdk.aws_elasticloadbalancingv2 import (
    ApplicationLoadBalancer,
    IApplicationLoadBalancer,
    IpAddressType,
)
from aws_cdk.aws_s3 import (
    Bucket,
    BucketEncryption,
    BlockPublicAccess,
)


class AlbStack(Stack):
    def __init__(self,
                 scope: Construct,
                 id: str,
                 vpc: IVpc,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Stack", "Common-Alb")

        self._alb = ApplicationLoadBalancer(self, "ALB",
            vpc=vpc,
            internet_facing=True,
            ip_address_type=IpAddressType.DUAL_STACK,
        )

        logs_bucket = Bucket(self, "AccessLogs",
           encryption=BucketEncryption.KMS_MANAGED,
           block_public_access=BlockPublicAccess.BLOCK_ALL,
        )
        self._alb.log_access_logs(logs_bucket)

    @property
    def alb(self) -> IApplicationLoadBalancer:
        return self._alb
