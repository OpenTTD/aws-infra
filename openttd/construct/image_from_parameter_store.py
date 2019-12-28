from aws_cdk.core import (
    Construct,
    StringConcat,
    Token,
)
from aws_cdk.aws_ssm import StringParameter

from openttd.construct.policy import Policy
from openttd.stack.common import parameter_store


class ImageFromParameterStore(Construct):
    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 parameter_name: str,
                 image_name: str,
                 policy: Policy) -> None:
        super().__init__(scope, id)

        parameter = parameter_store.add_string(parameter_name, default="1")
        # Make sure external processes can change this Parameter, to redeploy
        # a new version of the container.
        policy.add_parameter(parameter.parameter)

        tag = Token.as_string(StringParameter.value_for_string_parameter(self, parameter.name))
        self._image_ref = StringConcat().join(f"{image_name}:", tag)

    @property
    def image_ref(self):
        return self._image_ref
