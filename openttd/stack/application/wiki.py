from aws_cdk.core import (
    Construct,
    Duration,
    Stack,
    Tags,
)
from aws_cdk.aws_ecs import (
    EfsVolumeConfiguration,
    ICluster,
    IEc2Service,
    Secret,
    Volume,
)
from aws_cdk.aws_ec2 import (
    IVpc,
    SecurityGroup,
)
from aws_cdk.aws_efs import FileSystem
from aws_cdk.aws_iam import (
    ManagedPolicy,
    PolicyStatement,
)
from aws_cdk.aws_lambda import (
    Code,
    Function,
    Runtime,
)

from openttd.construct.ecs_https_container import ECSHTTPSContainer
from openttd.construct.policy import Policy
from openttd.enumeration import Deployment
from openttd.stack.common import parameter_store


class WikiStack(Stack):
    application_name = "Wiki"
    subdomain_name = "wiki"

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        deployment: Deployment,
        policy: Policy,
        cluster: ICluster,
        vpc: IVpc,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        policy.add_stack(self)

        efs_cache = FileSystem(
            self,
            "WikiCacheEFS",
            vpc=vpc,
        )
        efs_cache.connections.allow_default_port_from(cluster)

        if deployment == Deployment.PRODUCTION:
            desired_count = 1  # Currently this pod is stateful, and as such cannot be run more than once
            priority = 80
            memory = 384
            github_url = "git@github.com:OpenTTD/wiki-data.git"
            github_history_url = "https://github.com/OpenTTD/wiki-data"
            frontend_url = "https://wiki.openttd.org"
        else:
            desired_count = 1
            priority = 180
            memory = 128
            github_url = "git@github.com:OpenTTD/wiki-data-staging.git"
            github_history_url = "https://github.com/OpenTTD/wiki-data-staging"
            frontend_url = "https://wiki.staging.openttd.org"

        sentry_dsn = parameter_store.add_secure_string(f"/Wiki/{deployment.value}/SentryDSN").parameter
        user_github_client_id = parameter_store.add_secure_string(f"/Wiki/{deployment.value}/UserGithubClientId").parameter
        user_github_client_secret = parameter_store.add_secure_string(f"/Wiki/{deployment.value}/UserGithubClientSecret").parameter
        storage_github_private_key = parameter_store.add_secure_string(f"/Wiki/{deployment.value}/StorageGithubPrivateKey").parameter
        reload_secret = parameter_store.add_secure_string(f"/Wiki/{deployment.value}/ReloadSecret").parameter

        self.container = ECSHTTPSContainer(
            self,
            self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="ghcr.io/truebrain/truewiki",
            port=80,
            memory_limit_mib=memory,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--storage",
                "github",
                "--storage-github-url",
                github_url,
                "--storage-github-history-url",
                github_history_url,
                "--storage-folder",
                "/data",
                "--user",
                "github",
                "--frontend-url",
                frontend_url,
                "--cache-metadata-file",
                "/cache/metadata.json",
                "--cache-page-folder",
                "/cache-pages",
                "--bind",
                "0.0.0.0",
            ],
            environment={
                "TRUEWIKI_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "TRUEWIKI_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
                "TRUEWIKI_USER_GITHUB_CLIENT_ID": Secret.from_ssm_parameter(user_github_client_id),
                "TRUEWIKI_USER_GITHUB_CLIENT_SECRET": Secret.from_ssm_parameter(user_github_client_secret),
                "TRUEWIKI_STORAGE_GITHUB_PRIVATE_KEY": Secret.from_ssm_parameter(storage_github_private_key),
                "TRUEWIKI_RELOAD_SECRET": Secret.from_ssm_parameter(reload_secret),
            },
            volumes={
                "/cache": Volume(
                    name="cache",
                    efs_volume_configuration=EfsVolumeConfiguration(
                        file_system_id=efs_cache.file_system_id,
                    ),
                ),
            },
        )


class WikiReload(Stack):
    application_name = "WikiReload"

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
            code=Code.from_asset("./lambdas/wiki-reload"),
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
