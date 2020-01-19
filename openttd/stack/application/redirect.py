from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
)
from aws_cdk.aws_cloudfront import (
    LambdaEdgeEventType,
    LambdaFunctionAssociation,
)
from aws_cdk.aws_lambda import (
    Code,
    Runtime,
)
from aws_cdk.aws_s3 import (
    BlockPublicAccess,
    Bucket,
    BucketEncryption,
)

from openttd.construct.s3_cloud_front import S3CloudFront
from openttd.enumeration import Deployment
from openttd.stack.common import lambda_edge


class RedirectStack(Stack):
    application_name = "Redirect"
    subdomain_names = [
        "noai",
        "nogo",
    ]

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 deployment: Deployment,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Application", self.application_name)
        Tag.add(self, "Deployment", deployment.value)

        bucket_site = Bucket(self, "Site",
            block_public_access=BlockPublicAccess.BLOCK_ALL,
        )

        bucket_access_logs = Bucket(self, "AccessLogs",
            encryption=BucketEncryption.S3_MANAGED,
            block_public_access=BlockPublicAccess.BLOCK_ALL,
        )

        for subdomain_name in self.subdomain_names:
            func = lambda_edge.create_function(self, f"Redirect-{subdomain_name}",
                runtime=Runtime.NODEJS_10_X,
                handler="index.handler",
                code=Code.from_asset(f"./lambdas/domain-redirect-{subdomain_name}"),
            )

            S3CloudFront(self, f"S3CloudFront-{subdomain_name}",
                subdomain_name=subdomain_name,
                bucket_site=bucket_site,
                bucket_access_logs=bucket_access_logs,
                lambda_function_associations=LambdaFunctionAssociation(
                    event_type=LambdaEdgeEventType.ORIGIN_REQUEST,
                    lambda_function=func,
                ),
            )
