from aws_cdk.core import (
    Arn,
    ArnComponents,
    Construct,
    Stack,
    StringConcat,
    Tag,
)
from aws_cdk.aws_cloudfront import (
    Behavior,
    CfnDistribution,
    CloudFrontWebDistribution,
    LambdaEdgeEventType,
    LambdaFunctionAssociation,
    LoggingConfiguration,
    OriginAccessIdentity,
    PriceClass,
    SourceConfiguration,
    S3OriginConfig,
    ViewerCertificate,
)
from aws_cdk.aws_iam import (
    ManagedPolicy,
    PolicyStatement,
)
from aws_cdk.aws_lambda import (
    Code,
    Runtime,
)
from aws_cdk.aws_route53_targets import CloudFrontTarget
from aws_cdk.aws_s3 import (
    BlockPublicAccess,
    Bucket,
    BucketEncryption,
)

from openttd.construct.dns import (
    ARecord,
    AaaaRecord,
)
from openttd.enumeration import Deployment
from openttd.stack.common import certificate
from openttd.stack.common import lambda_edge


class DocsStack(Stack):
    application_name = "Docs"
    subdomain_name = "docs"

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 deployment: Deployment,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Application", self.application_name)
        Tag.add(self, "Deployment", deployment.value)

        oai = OriginAccessIdentity(self, "OAI")

        bucket = Bucket(self, "Docs",
           block_public_access=BlockPublicAccess.BLOCK_ALL,
        )
        bucket.grant_read(oai)
        logs_bucket = Bucket(self, "AccessLogs",
           encryption=BucketEncryption.S3_MANAGED,
           block_public_access=BlockPublicAccess.BLOCK_ALL,
        )

        cert = certificate.add_certificate(self.subdomain_name, region="us-east-1")

        func = lambda_edge.create_function(self, "DocsIndexRedirect",
            runtime=Runtime.NODEJS_10_X,
            handler="index.handler",
            code=Code.from_asset("./lambdas/index-redirect"),
        )

        distribution = CloudFrontWebDistribution(self, "CloudFront",
            origin_configs=[SourceConfiguration(
                s3_origin_source=S3OriginConfig(
                    s3_bucket_source=bucket,
                    origin_access_identity=oai,
                ),
                behaviors=[
                    Behavior(
                        is_default_behavior=True,
                        lambda_function_associations=[
                            LambdaFunctionAssociation(
                                event_type=LambdaEdgeEventType.ORIGIN_REQUEST,
                                lambda_function=func,
                            ),
                        ],
                    )
                ]
            )],
            enable_ip_v6=True,
            error_configurations=[
                CfnDistribution.CustomErrorResponseProperty(
                    error_code=404,
                    response_code=404,
                    response_page_path="/errors/404.html",
                ),
            ],
            price_class=PriceClass.PRICE_CLASS_100,
            logging_config=LoggingConfiguration(
                bucket=logs_bucket,
            ),
            viewer_certificate=ViewerCertificate.from_acm_certificate(
                certificate=cert.certificate,
                aliases=[cert.fqdn],
            ),
        )

        ARecord(self, f"{cert.fqdn}-ARecord",
            fqdn=cert.fqdn,
            target=CloudFrontTarget(distribution),
        )
        AaaaRecord(self, f"{cert.fqdn}-AaaaRecord",
            fqdn=cert.fqdn,
            target=CloudFrontTarget(distribution),
        )

        policy = ManagedPolicy(self, "Policy")
        policy.add_statements(PolicyStatement(
            actions=[
                "s3:DeleteObject",
                "s3:ListBucket",
                "s3:PutObject",
                "s3:PutObjectAcl",
            ],
            resources=[
                bucket.bucket_arn,
                StringConcat().join(bucket.bucket_arn, "/*")
            ],
        ))
        policy.add_statements(PolicyStatement(
            actions=[
                "cloudfront:CreateInvalidation",
            ],
            resources=[
                Arn.format(ArnComponents(
                    resource="distribution",
                    service="cloudfront",
                    region="",
                    resource_name=distribution.distribution_id,
                ), self),
            ],
        ))
