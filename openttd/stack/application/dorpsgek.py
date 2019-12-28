from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
)
from aws_cdk.aws_ecs import (
    ICluster,
    Secret,
)

from openttd.construct.ecs_https_container import ECSHTTPSContainer
from openttd.construct.policy import Policy
from openttd.enumeration import Deployment
from openttd.stack.common import parameter_store


class DorpsgekStack(Stack):
    application_name = "Dorpsgek"

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
            desired_count = 1
            priority = 30
        else:
            # This container only runs in production, as having multiple of
            # them currently serves no purpose.
            return

        sentry_dsn = parameter_store.add_secure_string("/Dorpsgek/SentryDSN").parameter
        github_app_id = parameter_store.add_secure_string("/Dorpsgek/GithubAppId").parameter
        github_app_private_key = parameter_store.add_secure_string("/Dorpsgek/GithubAppPrivateKey").parameter
        github_app_secret = parameter_store.add_secure_string("/Dorpsgek/GithubAppSecret").parameter

        ECSHTTPSContainer(self, self.application_name,
            subdomain_name="dorpsgek",
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="openttd/dorpsgek",
            port=80,
            memory_limit_mib=128,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            secrets={
                "DORPSGEK_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
                "DORPSGEK_GITHUB_APP_ID": Secret.from_ssm_parameter(github_app_id),
                "DORPSGEK_GITHUB_APP_PRIVATE_KEY": Secret.from_ssm_parameter(github_app_private_key),
                "DORPSGEK_GITHUB_APP_SECRET": Secret.from_ssm_parameter(github_app_secret),
            },
            )
