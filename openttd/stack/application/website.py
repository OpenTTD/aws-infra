from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
)
from aws_cdk.aws_ecs import ICluster

from openttd.construct.ecs_https_container import ECSHTTPSContainer
from openttd.construct.policy import Policy
from openttd.enumeration import Deployment


class WebsiteStack(Stack):
    application_name = "Website"

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
            desired_count = 2
            priority = 10
        else:
            desired_count = 1
            priority = 110

        ECSHTTPSContainer(self, self.application_name,
            subdomain_name="www",
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="openttd/website",
            port=80,
            memory_limit_mib=128,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            )
