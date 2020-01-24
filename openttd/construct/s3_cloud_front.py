from aws_cdk.core import (
    Arn,
    ArnComponents,
    Construct,
    StringConcat,
)
from aws_cdk.aws_cloudfront import (
    Behavior,
    CfnDistribution,
    CloudFrontWebDistribution,
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
from aws_cdk.aws_route53_targets import CloudFrontTarget
from aws_cdk.aws_s3 import (
    BlockPublicAccess,
    Bucket,
    BucketEncryption,
)
from typing import (
    List,
    Optional,
)

from openttd.construct.dns import (
    ARecord,
    AaaaRecord,
)
from openttd.stack.common import certificate


class S3CloudFront(Construct):
    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 subdomain_name: str,
                 additional_fqdns: Optional[List[str]] = None,
                 error_folder: Optional[str] = None,
                 lambda_function_associations: Optional[List[LambdaFunctionAssociation]] = None,
                 bucket_site: Optional[Bucket] = None,
                 bucket_access_logs: Optional[Bucket] = None,
                 ) -> None:
        super().__init__(scope, id)
        self.bucket_site = bucket_site

        if additional_fqdns is None:
            additional_fqdns = []

        # We restrict access to the S3 as much as possible; in result, we need
        # an OAI, so CloudFront can connect to it.
        oai = OriginAccessIdentity(self, "OAI",
            comment=f"OAI for {subdomain_name}",
        )

        if not self.bucket_site:
            self.bucket_site = Bucket(self, "Site",
                block_public_access=BlockPublicAccess.BLOCK_ALL,
            )
        self.bucket_site.grant_read(oai)

        if not bucket_access_logs:
            bucket_access_logs = Bucket(self, "AccessLogs",
                encryption=BucketEncryption.S3_MANAGED,
                block_public_access=BlockPublicAccess.BLOCK_ALL,
            )

        # CloudFront needs everything to be available in us-east-1
        cert = certificate.add_certificate(subdomain_name, region="us-east-1", additional_fqdns=additional_fqdns)

        error_configurations = None
        if error_folder:
            error_configurations = [
                CfnDistribution.CustomErrorResponseProperty(
                    error_code=404,
                    response_code=404,
                    response_page_path=f"{error_folder}/404.html",
                ),
            ]

        self.distribution = CloudFrontWebDistribution(self, "CloudFront",
            origin_configs=[SourceConfiguration(
                s3_origin_source=S3OriginConfig(
                    s3_bucket_source=self.bucket_site,
                    origin_access_identity=oai,
                ),
                behaviors=[
                    Behavior(
                        is_default_behavior=True,
                        lambda_function_associations=[
                            lambda_function_associations,
                        ],
                    )
                ]
            )],
            enable_ip_v6=True,
            error_configurations=error_configurations,
            price_class=PriceClass.PRICE_CLASS_100,
            logging_config=LoggingConfiguration(
                bucket=bucket_access_logs,
            ),
            viewer_certificate=ViewerCertificate.from_acm_certificate(
                certificate=cert.certificate,
                aliases=[cert.fqdn] + additional_fqdns,
            ),
        )

        ARecord(self, f"{cert.fqdn}-ARecord",
            fqdn=cert.fqdn,
            target=CloudFrontTarget(self.distribution),
        )
        AaaaRecord(self, f"{cert.fqdn}-AaaaRecord",
            fqdn=cert.fqdn,
            target=CloudFrontTarget(self.distribution),
        )


class S3CloudFrontPolicy(Construct):
    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 s3_cloud_front: S3CloudFront,
                 ) -> None:
        super().__init__(scope, id)

        policy = ManagedPolicy(self, "Policy")
        policy.add_statements(PolicyStatement(
            actions=[
                "s3:DeleteObject",
                "s3:ListBucket",
                "s3:PutObject",
                "s3:PutObjectAcl",
            ],
            resources=[
                s3_cloud_front.bucket_site.bucket_arn,
                StringConcat().join(s3_cloud_front.bucket_site.bucket_arn, "/*")
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
                    resource_name=s3_cloud_front.distribution.distribution_id,
                ), self.node.scope),
            ],
        ))
