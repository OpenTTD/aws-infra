from aws_cdk.core import (
    Construct,
    Stack,
    Tags,
)
from aws_cdk.aws_cloudfront import (
    LambdaEdgeEventType,
    LambdaFunctionAssociation,
)
from aws_cdk.aws_lambda import (
    Code,
    Runtime,
)

from openttd.construct.s3_cloud_front import (
    S3CloudFront,
    S3CloudFrontPolicy,
)
from openttd.enumeration import Deployment
from openttd.stack.common import lambda_edge


class FlysprayStack(Stack):
    application_name = "Flyspray"
    subdomain_name = "bugs"

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 deployment: Deployment,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        func = lambda_edge.create_function(self, f"Flyspray{deployment.value}IndexRedirect",
            runtime=Runtime.NODEJS_10_X,
            handler="index.handler",
            code=Code.from_asset("./lambdas/flyspray-redirect"),
        )

        s3_cloud_front = S3CloudFront(self, "S3CloudFront",
            subdomain_name=self.subdomain_name,
            error_folder="/errors",
            lambda_function_associations=[
                LambdaFunctionAssociation(
                    event_type=LambdaEdgeEventType.ORIGIN_REQUEST,
                    lambda_function=func,
                ),
            ],
        )

        S3CloudFrontPolicy(self, "S3cloudFrontPolicy",
            s3_cloud_front=s3_cloud_front,
        )
