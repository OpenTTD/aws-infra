from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
)
from aws_cdk.aws_ssm import StringParameter
from typing import Optional

from openttd.enumeration import Maturity
from openttd.stack.common import external

g_parameter_store = None  # type: Optional[ParameterStoreStack]


class ParameterStoreStack(Stack):
    """
    Stack to create SSM Parameters with.

    Parameters are created in a single stack, as many other stacks use the
    Parameters as input. For CloudFormation to work, those entries already
    have to exist before a stack can be created.
    """

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 maturity: Maturity,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        global g_parameter_store

        Tag.add(self, "Stack", "Common-ParameterStore")

        self._maturity = maturity.value

        if g_parameter_store is not None:
            raise Exception("Only a single ParameterStoreStack instance can exist")
        g_parameter_store = self

    def add_parameter(self, name: str, default: str) -> str:
        parameter_name = f"{self._maturity}-{name}"

        parameter = StringParameter(self, parameter_name,
            string_value=default,
            parameter_name=parameter_name,
        )
        external.add_parameter(parameter)

        return parameter_name


def add_parameter(name: str, default: str) -> str:
    if g_parameter_store is None:
        raise Exception("No ParameterStoreStack instance exists")

    return g_parameter_store.add_parameter(name, default=default)
