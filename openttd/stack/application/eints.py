from aws_cdk.core import (
    Construct,
    Stack,
    Tags,
)
from aws_cdk.aws_ecs import (
    EfsVolumeConfiguration,
    ICluster,
    Secret,
    Volume,
)
from aws_cdk.aws_ec2 import IVpc
from aws_cdk.aws_efs import FileSystem

from openttd.construct.ecs_https_container import ECSHTTPSContainer
from openttd.construct.policy import Policy
from openttd.enumeration import Deployment
from openttd.stack.common import parameter_store


class EintsStack(Stack):
    application_name = "Eints"
    subdomain_name = "translator"

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

        efs = FileSystem(
            self,
            "EintsEFS",
            vpc=vpc,
        )
        efs.connections.allow_default_port_from(cluster)

        if deployment == Deployment.PRODUCTION:
            desired_count = 1  # Currently this pod is stateful, and as such cannot be run more than once
            priority = 70
            memory = 512
        else:
            desired_count = 1
            priority = 170
            memory = 128

        github_org_api_token = parameter_store.add_secure_string(f"/Eints/{deployment.value}/GithubOrgApiToken").parameter
        github_oauth2_client_id = parameter_store.add_secure_string(f"/Eints/{deployment.value}/GithubOauth2ClientId").parameter
        github_oauth2_client_secret = parameter_store.add_secure_string(f"/Eints/{deployment.value}/GithubOauth2ClientSecret").parameter
        translators_password = parameter_store.add_secure_string(f"/Eints/{deployment.value}/TranslatorsPassword").parameter
        sentry_dsn = parameter_store.add_secure_string(f"/Eints/{deployment.value}/SentryDSN").parameter

        ECSHTTPSContainer(
            self,
            self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="ghcr.io/openttd/eints-openttd-github",
            port=80,
            memory_limit_mib=memory,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--server-host",
                "0.0.0.0",
                "--server-port",
                "80",
                "--server-mode",
                "production",
                "--authentication",
                "github",
                "--stable-languages",
                "stable_languages",
                "--unstable-languages",
                "unstable_languages",
                "--project-cache",
                "1",
                "--project-types",
                "openttd",
                "--project-types",
                "newgrf",
                "--project-types",
                "game-script",
                "--storage-format",
                "split-languages",
                "--data-format",
                "json",
                "--language-file-size",
                "10000000",
                "--num-backup-files",
                "1",
                "--max-num-changes",
                "5",
                "--min-num-changes",
                "2",
                "--change-stable-age",
                "600",
                "--github-organization",
                "OpenTTD",
            ],
            environment={
                "EINTS_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "EINTS_GITHUB_ORG_API_TOKEN": Secret.from_ssm_parameter(github_org_api_token),
                "EINTS_GITHUB_OAUTH2_CLIENT_ID": Secret.from_ssm_parameter(github_oauth2_client_id),
                "EINTS_GITHUB_OAUTH2_CLIENT_SECRET": Secret.from_ssm_parameter(github_oauth2_client_secret),
                "EINTS_TRANSLATORS_PASSWORD": Secret.from_ssm_parameter(translators_password),
                "EINTS_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
            },
            volumes={
                "/data": Volume(
                    name="data",
                    efs_volume_configuration=EfsVolumeConfiguration(
                        file_system_id=efs.file_system_id,
                    ),
                )
            },
        )
