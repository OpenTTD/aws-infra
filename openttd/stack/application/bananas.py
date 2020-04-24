from aws_cdk.core import (
    Construct,
    Stack,
    StringConcat,
    Tag,
)
from aws_cdk.aws_cloudfront import (
    PriceClass,
    ViewerProtocolPolicy,
)
from aws_cdk.aws_ecs import (
    ICluster,
    Secret,
)
from aws_cdk.aws_ec2 import Port
from aws_cdk.aws_iam import PolicyStatement
from aws_cdk.aws_s3 import Bucket
from typing import (
    List,
    Optional,
)

from openttd.construct.ecs_https_container import ECSHTTPSContainer
from openttd.construct.policy import Policy
from openttd.construct.s3_cloud_front import (
    S3CloudFront,
    S3CloudFrontPolicy,
)
from openttd.enumeration import Deployment
from openttd.stack.common import (
    dns,
    nlb_self as nlb,
    parameter_store,
)


class BananasCdnStack(Stack):
    application_name = "BananasCdn"
    subdomain_name = "bananas.cdn"

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 deployment: Deployment,
                 additional_fqdns: Optional[List[str]] = None,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Application", self.application_name)
        Tag.add(self, "Deployment", deployment.value)

        s3_cloud_front = S3CloudFront(self, "S3CloudFront",
            subdomain_name=self.subdomain_name,
            error_folder="/errors",
            price_class=PriceClass.PRICE_CLASS_ALL,
            additional_fqdns=additional_fqdns,
            viewer_protocol_policy=ViewerProtocolPolicy.ALLOW_ALL,  # OpenTTD client doesn't support HTTPS
        )
        self.bucket = s3_cloud_front.bucket_site

        S3CloudFrontPolicy(self, "S3cloudFrontPolicy",
            s3_cloud_front=s3_cloud_front,
            with_s3_get_object_access=True,
        )


class BananasApiStack(Stack):
    application_name = "BananasApi"
    subdomain_name = "api.bananas"

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 deployment: Deployment,
                 policy: Policy,
                 cluster: ICluster,
                 bucket: Bucket,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Application", self.application_name)
        Tag.add(self, "Deployment", deployment.value)

        policy.add_stack(self)

        if deployment == Deployment.PRODUCTION:
            desired_count = 1  # Currently this pod is stateful, and as such cannot be run more than once
            tus_priority = 40
            priority = 42
            github_url = "git@github.com:OpenTTD/BaNaNaS.git"
            client_file = "clients-production.yaml"
        else:
            desired_count = 1
            tus_priority = 140
            priority = 142
            github_url = "git@github.com:OpenTTD/BaNaNaS-staging.git"
            client_file = "clients-staging.yaml"

        sentry_dsn = parameter_store.add_secure_string(f"/BananasApi/{deployment.value}/SentryDSN").parameter
        user_github_client_id = parameter_store.add_secure_string(f"/BananasApi/{deployment.value}/UserGithubClientId").parameter
        user_github_client_secret = parameter_store.add_secure_string(f"/BananasApi/{deployment.value}/UserGithubClientSecret").parameter
        index_github_private_key = parameter_store.add_secure_string(f"/BananasApi/{deployment.value}/IndexGithubPrivateKey").parameter
        reload_secret = parameter_store.add_secure_string(f"/BananasApi/{deployment.value}/ReloadSecret").parameter

        container = ECSHTTPSContainer(self, self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="openttd/bananas-api",
            port=80,
            memory_limit_mib=128,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--storage", "s3",
                "--storage-s3-bucket", bucket.bucket_name,
                "--index", "github",
                "--index-github-url", github_url,
                "--client-file", client_file,
                "--user", "github",
                "--bind", "0.0.0.0",
                "--behind-proxy",
            ],
            environment={
                "BANANAS_API_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "BANANAS_API_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
                "BANANAS_API_USER_GITHUB_CLIENT_ID": Secret.from_ssm_parameter(user_github_client_id),
                "BANANAS_API_USER_GITHUB_CLIENT_SECRET": Secret.from_ssm_parameter(user_github_client_secret),
                "BANANAS_API_INDEX_GITHUB_PRIVATE_KEY": Secret.from_ssm_parameter(index_github_private_key),
                "BANANAS_API_RELOAD_SECRET": Secret.from_ssm_parameter(reload_secret),
            },
        )
        container.add_port(1080)
        container.add_target(
            subdomain_name=self.subdomain_name,
            port=1080,
            priority=tus_priority,
            path_pattern="/new-package/tus/*",
        )

        container.task_role.add_to_policy(PolicyStatement(
            actions=[
                "s3:PutObject",
                "s3:PutObjectAcl",
            ],
            resources=[
                StringConcat().join(bucket.bucket_arn, "/*"),
            ]
        ))


class BananasServerStack(Stack):
    application_name = "BananasServer"
    subdomain_name = "binaries"
    path_pattern = "/bananas"
    nlb_subdomain_name = "content"

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 deployment: Deployment,
                 policy: Policy,
                 cluster: ICluster,
                 bucket: Bucket,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Application", self.application_name)
        Tag.add(self, "Deployment", deployment.value)

        policy.add_stack(self)

        if deployment == Deployment.PRODUCTION:
            desired_count = 2
            priority = 44
            github_url = "https://github.com/OpenTTD/BaNaNaS"
            content_port = 3978
        else:
            desired_count = 1
            priority = 144
            github_url = "https://github.com/OpenTTD/BaNaNaS-staging"
            content_port = 4978

        cdn_fqdn = dns.subdomain_to_fqdn("bananas.cdn")
        cdn_url = f"http://{cdn_fqdn}"

        sentry_dsn = parameter_store.add_secure_string(f"/BananasServer/{deployment.value}/SentryDSN").parameter
        reload_secret = parameter_store.add_secure_string(f"/BananasServer/{deployment.value}/ReloadSecret").parameter

        container = ECSHTTPSContainer(self, self.application_name,
            subdomain_name=self.subdomain_name,
            path_pattern=self.path_pattern,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="openttd/bananas-server",
            port=80,
            memory_limit_mib=128,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--storage", "s3",
                "--storage-s3-bucket", bucket.bucket_name,
                "--index", "github",
                "--index-github-url", github_url,
                "--cdn-url", cdn_url,
                "--bind", "0.0.0.0",
                "--content-port", str(content_port),
                "--proxy-protocol",
            ],
            environment={
                "BANANAS_SERVER_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "BANANAS_SERVER_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
                "BANANAS_SERVER_RELOAD_SECRET": Secret.from_ssm_parameter(reload_secret),
            },
        )

        container.add_port(content_port)
        nlb.add_nlb(container.service, Port.tcp(content_port), self.nlb_subdomain_name, "BaNaNaS Server")

        container.task_role.add_to_policy(PolicyStatement(
            actions=[
                "s3:ListBucket",
            ],
            resources=[
                bucket.bucket_arn,
            ]
        ))


class BananasFrontendWebStack(Stack):
    application_name = "BananasFrontendWeb"
    subdomain_name = "bananas"

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 deployment: Deployment,
                 policy: Policy,
                 cluster: ICluster,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Application", self.application_name)
        Tag.add(self, "Deployment", deployment.value)

        policy.add_stack(self)

        if deployment == Deployment.PRODUCTION:
            desired_count = 1  # Currently this pod is stateful, and as such cannot be run more than once
            priority = 46
        else:
            desired_count = 1
            priority = 146

        api_fqdn = dns.subdomain_to_fqdn("api.bananas")
        api_url = f"https://{api_fqdn}"
        frontend_fqdn = dns.subdomain_to_fqdn(self.subdomain_name)
        frontend_url = f"https://{frontend_fqdn}"

        sentry_dsn = parameter_store.add_secure_string(f"/BananasFrontendWeb/{deployment.value}/SentryDSN").parameter

        ECSHTTPSContainer(self, self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="openttd/bananas-frontend-web",
            port=80,
            memory_limit_mib=128,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--authentication-method", "github",
                "--api-url", api_url,
                "--frontend-url", frontend_url,
                "run",
                "-p", "80",
                "-h", "0.0.0.0",
            ],
            environment={
                "WEBCLIENT_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "WEBCLIENT_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
            },
        )
