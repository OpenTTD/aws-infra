from aws_cdk.core import (
    Construct,
    Stack,
    Tags,
)
from aws_cdk.aws_cloudfront import (
    LambdaEdgeEventType,
    LambdaFunctionAssociation,
    PriceClass,
)
from aws_cdk.aws_lambda import (
    Code,
    Runtime,
)
from typing import (
    List,
    Optional,
)

from openttd.construct.s3_cloud_front import (
    S3CloudFront,
    S3CloudFrontPolicy,
)
from openttd.enumeration import Deployment
from openttd.stack.common import lambda_edge


class CdnStack(Stack):
    application_name = "Cdn"
    subdomain_name = "cdn"

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        deployment: Deployment,
        additional_fqdns: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        func = lambda_edge.create_function(
            self,
            "CdnIndexRedirect",
            runtime=Runtime.NODEJS_10_X,
            handler="index.handler",
            code=Code.from_asset("./lambdas/index-redirect"),
        )

        s3_cloud_front = S3CloudFront(
            self,
            "S3CloudFront",
            subdomain_name=self.subdomain_name,
            error_folder="/errors",
            lambda_function_associations=[
                LambdaFunctionAssociation(
                    event_type=LambdaEdgeEventType.ORIGIN_REQUEST,
                    lambda_function=func,
                ),
            ],
            additional_fqdns=additional_fqdns,
            price_class=PriceClass.PRICE_CLASS_ALL,
        )

        S3CloudFrontPolicy(
            self,
            "S3cloudFrontPolicy",
            s3_cloud_front=s3_cloud_front,
            with_s3_get_object_access=True,
        )
