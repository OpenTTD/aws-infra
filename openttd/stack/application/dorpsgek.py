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


class DorpsgekStack(Stack):
    application_name = "Dorpsgek"
    subdomain_name = "dorpsgek"

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

        efs_seen = FileSystem(
            self,
            "DorpsGekSeenEFS",
            vpc=vpc,
        )
        efs_seen.connections.allow_default_port_from(cluster)
        efs_logs = FileSystem(
            self,
            "DorpsGekLogsEFS",
            vpc=vpc,
        )
        efs_logs.connections.allow_default_port_from(cluster)

        if deployment == Deployment.PRODUCTION:
            desired_count = 1
            priority = 30
            addressed_by = "@"
            irc_username = "DorpsGek"
            channels = [
                "--channel",
                "dorpsgek",
                "--channel",
                "openttd,public",
                "--channel",
                "openttd.dev,public",
                "--channel",
                "openttd.notice",
                "--channel",
                "openttd.tgp",
                "--channel",
                "opendune,public",
            ]
        else:
            desired_count = 1
            priority = 130
            addressed_by = "%"
            irc_username = "DorpsGek_ivs"
            channels = [
                "--channel",
                "dorpsgek",
                "--channel",
                "dorpsgek-test,public",
            ]

        sentry_dsn = parameter_store.add_secure_string(f"/Dorpsgek/{deployment.value}/SentryDSN").parameter
        github_app_id = parameter_store.add_secure_string(f"/Dorpsgek/{deployment.value}/GithubAppId").parameter
        github_app_private_key = parameter_store.add_secure_string(f"/Dorpsgek/{deployment.value}/GithubAppPrivateKey").parameter
        github_app_secret = parameter_store.add_secure_string(f"/Dorpsgek/{deployment.value}/GithubAppSecret").parameter
        nickserv_password = parameter_store.add_secure_string(f"/Dorpsgek/{deployment.value}/NickservPassword").parameter

        ECSHTTPSContainer(
            self,
            self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="ghcr.io/openttd/dorpsgek",
            port=80,
            memory_limit_mib=96,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--irc-username",
                irc_username,
                "--nickserv-username",
                irc_username,
                "--addressed-by",
                addressed_by,
            ]
            + channels,
            environment={
                "DORPSGEK_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "DORPSGEK_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
                "DORPSGEK_GITHUB_APP_ID": Secret.from_ssm_parameter(github_app_id),
                "DORPSGEK_GITHUB_APP_PRIVATE_KEY": Secret.from_ssm_parameter(github_app_private_key),
                "DORPSGEK_GITHUB_APP_SECRET": Secret.from_ssm_parameter(github_app_secret),
                "DORPSGEK_NICKSERV_PASSWORD": Secret.from_ssm_parameter(nickserv_password),
            },
            volumes={
                "/code/data": Volume(
                    name="data",
                    efs_volume_configuration=EfsVolumeConfiguration(
                        file_system_id=efs_seen.file_system_id,
                    ),
                ),
                "/code/logs/ChannelLogger": Volume(
                    name="logs",
                    efs_volume_configuration=EfsVolumeConfiguration(
                        file_system_id=efs_logs.file_system_id,
                    ),
                ),
            },
        )
