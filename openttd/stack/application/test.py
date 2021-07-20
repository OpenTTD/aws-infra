from aws_cdk.core import (
    Construct,
    CfnOutput,
    Stack,
    Tags,
)

from openttd.construct.image_from_parameter_store import ImageFromParameterStore
from openttd.construct.policy import Policy
from openttd.enumeration import Deployment


class TestStack(Stack):
    """Test Stack for actions repository, so we can validate deploy-aws action works."""

    application_name = "Test"

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        deployment: Deployment,
        policy: Policy,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        policy.add_stack(self)

        parameter = ImageFromParameterStore(
            self,
            "ImageName",
            parameter_name=f"/Version/{deployment.value}/{self.application_name}",
            image_name="test",
            policy=policy,
        )

        CfnOutput(self, "Test", value=parameter.image_ref, export_name="Test")
