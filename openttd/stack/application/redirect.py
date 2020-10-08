from aws_cdk.core import (
    Construct,
    Stack,
    Tags,
)
from aws_cdk.aws_cloudfront import (
    EdgeLambda,
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
from openttd.construct.s3_cloud_front_v2 import S3CloudFrontV2
from openttd.enumeration import Deployment
from openttd.stack.common import lambda_edge


class RedirectStack(Stack):
    application_name = "Redirect"
    subdomain_names = [
        "download",
        "farm",
        "forum",
        "github",
        "grfsearch",
        "nightly",
        "noai",
        "nogo",
        "proxy.binaries",
        "root",
        "security",
    ]

    def __init__(self, scope: Construct, id: str, *, deployment: Deployment, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        bucket_site = Bucket(
            self,
            "Site",
            block_public_access=BlockPublicAccess.BLOCK_ALL,
        )

        bucket_access_logs = Bucket(
            self,
            "AccessLogs",
            encryption=BucketEncryption.S3_MANAGED,
            block_public_access=BlockPublicAccess.BLOCK_ALL,
        )

        for subdomain_name in self.subdomain_names:
            func_version = lambda_edge.create_function(
                self,
                f"Redirect-{subdomain_name}-{deployment.value}",
                runtime=Runtime.NODEJS_10_X,
                handler="index.handler",
                code=Code.from_asset(f"./lambdas/redirect-{subdomain_name}"),
            )

            if subdomain_name == "grfsearch":
                S3CloudFrontV2(
                    self,
                    f"S3CloudFront-{subdomain_name}",
                    subdomain_name=subdomain_name,
                    bucket_site=bucket_site,
                    bucket_access_logs=bucket_access_logs,
                    edge_lambdas=[
                        EdgeLambda(
                            event_type=LambdaEdgeEventType.ORIGIN_REQUEST,
                            function_version=func_version,
                        ),
                    ],
                    forward_query_string=True,
                    forward_query_string_cache_keys=["do", "q"],
                )
            else:
                S3CloudFront(
                    self,
                    f"S3CloudFront-{subdomain_name}",
                    subdomain_name=subdomain_name,
                    bucket_site=bucket_site,
                    bucket_access_logs=bucket_access_logs,
                    lambda_function_associations=[
                        LambdaFunctionAssociation(
                            event_type=LambdaEdgeEventType.ORIGIN_REQUEST,
                            lambda_function=func_version,
                        ),
                    ],
                )
