from aws_cdk.core import Construct
from aws_cdk.aws_cloudfront import (
    BehaviorOptions,
    CachePolicy,
    CacheQueryStringBehavior,
    Distribution,
    EdgeLambda,
    ErrorResponse,
    PriceClass,
    ViewerProtocolPolicy,
)
from aws_cdk.aws_cloudfront_origins import S3Origin
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


class S3CloudFrontV2(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        subdomain_name: str,
        additional_fqdns: Optional[List[str]] = None,
        error_folder: Optional[str] = None,
        forward_query_string_cache_keys: Optional[List[str]] = None,
        edge_lambdas: Optional[List[EdgeLambda]] = None,
        bucket_site: Optional[Bucket] = None,
        bucket_access_logs: Optional[Bucket] = None,
        price_class: Optional[PriceClass] = PriceClass.PRICE_CLASS_100,
        viewer_protocol_policy: Optional[ViewerProtocolPolicy] = ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    ) -> None:
        super().__init__(scope, id)
        self.bucket_site = bucket_site

        if additional_fqdns is None:
            additional_fqdns = []

        if not self.bucket_site:
            self.bucket_site = Bucket(
                self,
                "Site",
                block_public_access=BlockPublicAccess.BLOCK_ALL,
            )

        if not bucket_access_logs:
            bucket_access_logs = Bucket(
                self,
                "AccessLogs",
                encryption=BucketEncryption.S3_MANAGED,
                block_public_access=BlockPublicAccess.BLOCK_ALL,
            )

        # CloudFront needs everything to be available in us-east-1
        cert = certificate.add_certificate(subdomain_name, region="us-east-1", additional_fqdns=additional_fqdns)

        error_responses = None
        if error_folder:
            error_responses = [
                ErrorResponse(
                    http_status=404,
                    response_http_status=404,
                    response_page_path=f"{error_folder}/404.html",
                )
            ]

        if forward_query_string_cache_keys is None:
            query_string_behaviour = CacheQueryStringBehavior.none()
        else:
            query_string_behaviour = CacheQueryStringBehavior.allow_list(*forward_query_string_cache_keys)

        self.distribution = Distribution(
            self,
            "CloudFront",
            default_behavior=BehaviorOptions(
                origin=S3Origin(
                    bucket=self.bucket_site,
                ),
                viewer_protocol_policy=viewer_protocol_policy,
                edge_lambdas=edge_lambdas,
                cache_policy=CachePolicy(
                    self,
                    "CachePolicy",
                    query_string_behavior=query_string_behaviour,
                ),
            ),
            domain_names=[cert.fqdn] + additional_fqdns,
            certificate=cert.certificate,
            enable_logging=True,
            log_bucket=bucket_access_logs,
            price_class=price_class,
            enable_ipv6=True,
            error_responses=error_responses,
        )

        ARecord(
            self,
            f"{cert.fqdn}-ARecord",
            fqdn=cert.fqdn,
            target=CloudFrontTarget(self.distribution),
        )
        AaaaRecord(
            self,
            f"{cert.fqdn}-AaaaRecord",
            fqdn=cert.fqdn,
            target=CloudFrontTarget(self.distribution),
        )
