from aws_cdk.core import (
    Construct,
    Stack,
    Tags,
)
from aws_cdk.aws_certificatemanager import (
    DnsValidatedCertificate,
    ValidationMethod,
)
from aws_cdk.aws_cloudfront import (
    LambdaEdgeEventType,
    LambdaFunctionAssociation,
)
from aws_cdk.aws_lambda import (
    Code,
    Runtime,
)
import aws_cdk.aws_route53 as route53
from aws_cdk.aws_route53 import (
    HostedZone,
    RecordTarget,
)
from aws_cdk.aws_route53_targets import CloudFrontTarget

from openttd.construct.s3_cloud_front import (
    S3CloudFront,
    S3CloudFrontPolicy,
)
from openttd.enumeration import Deployment
from openttd.stack.common import lambda_edge
from openttd.stack.common.certificate import CertificateResult


class OpenttdComStack(Stack):
    application_name = "openttd-com"
    subdomain_name = "www"

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 deployment: Deployment,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        hosted_zone = HostedZone.from_lookup(self, "Zone",
            domain_name="openttd.com",
        )
        fqdn = "www.openttd.com"

        certificate = DnsValidatedCertificate(self, f"OpenttdCom-Certificate",
            hosted_zone=hosted_zone,
            domain_name=fqdn,
            subject_alternative_names=["*.openttd.com", "openttd.com"],
            region="us-east-1",
            validation_method=ValidationMethod.DNS,
        )

        func = lambda_edge.create_function(self, "OpenttdComRedirect",
            runtime=Runtime.NODEJS_10_X,
            handler="index.handler",
            code=Code.from_asset("./lambdas/openttd-com-redirect"),
        )

        s3_cloud_front = S3CloudFront(self, "S3CloudFront",
            subdomain_name=fqdn,
            cert=CertificateResult(certificate, certificate.certificate_arn, fqdn),
            additional_fqdns=["*.openttd.com", "openttd.com"],
            lambda_function_associations=[
                LambdaFunctionAssociation(
                    event_type=LambdaEdgeEventType.ORIGIN_REQUEST,
                    lambda_function=func,
                ),
            ],
            no_dns=True,
        )

        S3CloudFrontPolicy(self, "S3cloudFrontPolicy",
            s3_cloud_front=s3_cloud_front,
        )

        for record_name in ("www", "www.aws", None):
            route53.ARecord(self, f"{record_name}.openttd.com-ARecord",
                target=RecordTarget.from_alias(CloudFrontTarget(s3_cloud_front.distribution)),
                zone=hosted_zone,
                record_name=record_name,
            )
            route53.AaaaRecord(self, f"{record_name}.openttd.com-AaaaRecord",
                target=RecordTarget.from_alias(CloudFrontTarget(s3_cloud_front.distribution)),
                zone=hosted_zone,
                record_name=record_name,
            )
