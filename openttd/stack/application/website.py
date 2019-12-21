from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
)
from aws_cdk.aws_ecs import ICluster

from openttd.construct.ecs_https_container import ECSHTTPSContainer
from openttd.enumeration import Deployment


class WebsiteStack(Stack):
    application = "Website"

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 deployment: Deployment,
                 cluster: ICluster,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Application", self.application)
        Tag.add(self, "Deployment", deployment.value)

        desired_count = 1
        if deployment == Deployment.PRODUCTION:
            desired_count = 2

        ECSHTTPSContainer(self, self.application,
            subdomain_name="www",
            application_name=f"{deployment.value}-{self.application}",
            image_name="openttd/website",
            port=80,
            memory_limit_mib=128,
            desired_count=desired_count,
            cluster=cluster,
            )
