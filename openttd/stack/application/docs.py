from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
)
from aws_cdk.aws_cloudfront import (
    Behavior,
    CloudFrontWebDistribution,
    LoggingConfiguration,
    OriginAccessIdentity,
    PriceClass,
    SourceConfiguration,
    S3OriginConfig,
    ViewerCertificate,
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

        distribution = CloudFrontWebDistribution(self, "CloudFront",
            origin_configs=[SourceConfiguration(
                s3_origin_source=S3OriginConfig(
                    s3_bucket_source=bucket,
                    origin_access_identity=oai,
                ),
                origin_path="/live",
                behaviors=[Behavior(is_default_behavior=True)]
            )],
            enable_ip_v6=True,
            price_class=PriceClass.PRICE_CLASS_100,
            logging_config=LoggingConfiguration(
                bucket=logs_bucket,
            ),
            viewer_certificate=ViewerCertificate.from_acm_certificate(
                certificate=cert.certificate,
                aliases=[cert.fqdn],
            )
        )

        ARecord(self, f"{cert.fqdn}-ARecord",
            fqdn=cert.fqdn,
            target=CloudFrontTarget(distribution),
        )
        AaaaRecord(self, f"{cert.fqdn}-AaaaRecord",
            fqdn=cert.fqdn,
            target=CloudFrontTarget(distribution),
        )
