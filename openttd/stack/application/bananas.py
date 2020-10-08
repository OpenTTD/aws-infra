from aws_cdk.core import (
    Construct,
    Duration,
    Stack,
    StringConcat,
    Tags,
)
from aws_cdk.aws_cloudfront import (
    LambdaEdgeEventType,
    LambdaFunctionAssociation,
    PriceClass,
    ViewerProtocolPolicy,
)
from aws_cdk.aws_ecs import (
    ICluster,
    IEc2Service,
    Secret,
)
from aws_cdk.aws_ec2 import (
    IVpc,
    Port,
    SecurityGroup,
)
from aws_cdk.aws_iam import (
    ManagedPolicy,
    PolicyStatement,
)
from aws_cdk.aws_lambda import (
    Code,
    Function,
    Runtime,
)
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
    lambda_edge,
    nlb_self as nlb,
    parameter_store,
)


class BananasCdnStack(Stack):
    application_name = "BananasCdn"
    subdomain_name = "bananas.cdn"

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        deployment: Deployment,
        additional_fqdns: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        func = lambda_edge.create_function(
            self,
            f"BananasCdnRedirect{deployment.value}",
            runtime=Runtime.NODEJS_10_X,
            handler="index.handler",
            code=Code.from_asset("./lambdas/bananas-cdn"),
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
            price_class=PriceClass.PRICE_CLASS_ALL,
            additional_fqdns=additional_fqdns,
            viewer_protocol_policy=ViewerProtocolPolicy.ALLOW_ALL,  # OpenTTD client doesn't support HTTPS
        )
        self.bucket = s3_cloud_front.bucket_site

        S3CloudFrontPolicy(
            self,
            "S3cloudFrontPolicy",
            s3_cloud_front=s3_cloud_front,
            with_s3_get_object_access=True,
        )


class BananasApiStack(Stack):
    application_name = "BananasApi"
    subdomain_name = "api.bananas"

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        deployment: Deployment,
        policy: Policy,
        cluster: ICluster,
        bucket: Bucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        policy.add_stack(self)

        if deployment == Deployment.PRODUCTION:
            desired_count = 1  # Currently this pod is stateful, and as such cannot be run more than once
            tus_priority = 40
            priority = 42
            memory = 256
            github_url = "git@github.com:OpenTTD/BaNaNaS.git"
            client_file = "clients-production.yaml"
        else:
            desired_count = 1
            tus_priority = 140
            priority = 142
            memory = 96
            github_url = "git@github.com:OpenTTD/BaNaNaS-staging.git"
            client_file = "clients-staging.yaml"

        sentry_dsn = parameter_store.add_secure_string(f"/BananasApi/{deployment.value}/SentryDSN").parameter
        user_github_client_id = parameter_store.add_secure_string(f"/BananasApi/{deployment.value}/UserGithubClientId").parameter
        user_github_client_secret = parameter_store.add_secure_string(f"/BananasApi/{deployment.value}/UserGithubClientSecret").parameter
        index_github_private_key = parameter_store.add_secure_string(f"/BananasApi/{deployment.value}/IndexGithubPrivateKey").parameter
        reload_secret = parameter_store.add_secure_string(f"/BananasApi/{deployment.value}/ReloadSecret").parameter

        self.container = ECSHTTPSContainer(
            self,
            self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="ghcr.io/openttd/bananas-api",
            port=80,
            memory_limit_mib=memory,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--storage",
                "s3",
                "--storage-s3-bucket",
                bucket.bucket_name,
                "--index",
                "github",
                "--index-github-url",
                github_url,
                "--client-file",
                client_file,
                "--user",
                "github",
                "--bind",
                "0.0.0.0",
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
        self.container.add_port(1080)
        self.container.add_target(
            subdomain_name=self.subdomain_name,
            port=1080,
            priority=tus_priority,
            path_pattern="/new-package/tus/*",
        )

        self.container.task_role.add_to_policy(
            PolicyStatement(
                actions=[
                    "s3:PutObject",
                    "s3:PutObjectAcl",
                ],
                resources=[
                    StringConcat().join(bucket.bucket_arn, "/*"),
                ],
            )
        )


class BananasServerStack(Stack):
    application_name = "BananasServer"
    subdomain_name = "binaries"
    path_pattern = "/bananas"
    nlb_subdomain_name = "content"

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        deployment: Deployment,
        policy: Policy,
        cluster: ICluster,
        bucket: Bucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        policy.add_stack(self)

        if deployment == Deployment.PRODUCTION:
            desired_count = 2
            priority = 44
            memory = 256
            github_url = "https://github.com/OpenTTD/BaNaNaS"
            content_port = 3978
            bootstrap_command = ["--bootstrap-unique-id", "4f474658"]
        else:
            desired_count = 1
            priority = 144
            memory = 128
            github_url = "https://github.com/OpenTTD/BaNaNaS-staging"
            content_port = 4978
            bootstrap_command = []

        cdn_fqdn = dns.subdomain_to_fqdn("bananas.cdn")
        cdn_url = f"http://{cdn_fqdn}"

        sentry_dsn = parameter_store.add_secure_string(f"/BananasServer/{deployment.value}/SentryDSN").parameter
        reload_secret = parameter_store.add_secure_string(f"/BananasServer/{deployment.value}/ReloadSecret").parameter

        command = [
            "--storage",
            "s3",
            "--storage-s3-bucket",
            bucket.bucket_name,
            "--index",
            "github",
            "--index-github-url",
            github_url,
            "--cdn-url",
            cdn_url,
            "--bind",
            "0.0.0.0",
            "--content-port",
            str(content_port),
            "--proxy-protocol",
        ]
        command.extend(bootstrap_command)

        self.container = ECSHTTPSContainer(
            self,
            self.application_name,
            subdomain_name=self.subdomain_name,
            path_pattern=self.path_pattern,
            allow_via_http=True,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="ghcr.io/openttd/bananas-server",
            port=80,
            memory_limit_mib=memory,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=command,
            environment={
                "BANANAS_SERVER_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "BANANAS_SERVER_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
                "BANANAS_SERVER_RELOAD_SECRET": Secret.from_ssm_parameter(reload_secret),
            },
        )

        self.container.add_port(content_port)
        nlb.add_nlb(self, self.container.service, Port.tcp(content_port), self.nlb_subdomain_name, "BaNaNaS Server")

        self.container.task_role.add_to_policy(
            PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket",
                ],
                resources=[
                    bucket.bucket_arn,
                    StringConcat().join(bucket.bucket_arn, "/*"),
                ],
            )
        )


class BananasFrontendWebStack(Stack):
    application_name = "BananasFrontendWeb"
    subdomain_name = "bananas"

    def __init__(self, scope: Construct, id: str, *, deployment: Deployment, policy: Policy, cluster: ICluster, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

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

        ECSHTTPSContainer(
            self,
            self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="ghcr.io/openttd/bananas-frontend-web",
            port=80,
            memory_limit_mib=64,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--api-url",
                api_url,
                "--frontend-url",
                frontend_url,
                "run",
                "-p",
                "80",
                "-h",
                "0.0.0.0",
            ],
            environment={
                "WEBCLIENT_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "WEBCLIENT_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
            },
        )


class BananasReload(Stack):
    application_name = "BananasReload"

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        vpc: IVpc,
        cluster: ICluster,
        service: IEc2Service,
        ecs_security_group: SecurityGroup,
        deployment: Deployment,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        security_group = SecurityGroup(
            self,
            "LambdaSG",
            vpc=vpc,
        )

        lambda_func = Function(
            self,
            "ReloadLambda",
            code=Code.from_asset("./lambdas/bananas-reload"),
            handler="index.lambda_handler",
            runtime=Runtime.PYTHON_3_8,
            timeout=Duration.seconds(120),
            environment={
                "CLUSTER": cluster.cluster_arn,
                "SERVICE": service.service_arn,
            },
            vpc=vpc,
            security_groups=[security_group, ecs_security_group],
            reserved_concurrent_executions=1,
        )
        lambda_func.add_to_role_policy(
            PolicyStatement(
                actions=[
                    "ec2:DescribeInstances",
                    "ecs:DescribeContainerInstances",
                    "ecs:DescribeTasks",
                    "ecs:ListContainerInstances",
                    "ecs:ListServices",
                    "ecs:ListTagsForResource",
                    "ecs:ListTasks",
                ],
                resources=[
                    "*",
                ],
            )
        )

        policy = ManagedPolicy(self, "Policy")
        policy.add_statements(
            PolicyStatement(
                actions=[
                    "lambda:InvokeFunction",
                ],
                resources=[lambda_func.function_arn],
            )
        )
