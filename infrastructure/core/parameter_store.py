from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
)
from aws_cdk.aws_ssm import StringParameter


class ParameterStoreStack(Stack):
    """
    Stack to create SSM Parameters with.

    This is done because parameters have to exist before stacks use them.
    So by creating a dedicated stack to create parameters, we can enforce this
    behaviour happening.
    """

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Stack", "ParameterStore")

    def add_parameter(self, name, default=None):
        StringParameter(self, name,
            string_value=default,
            parameter_name=name,
        )
