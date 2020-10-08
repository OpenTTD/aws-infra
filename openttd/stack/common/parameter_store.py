import boto3

from aws_cdk.core import (
    Construct,
    Stack,
    Tags,
)
from aws_cdk.aws_ssm import StringParameter
from typing import Optional

from openttd.enumeration import Maturity

g_parameter_store = None  # type: Optional[ParameterStoreStack]
ssm_client = boto3.client("ssm")


class ParameterResult:
    def __init__(self, parameter, name):
        self.parameter = parameter
        self.name = name


class ParameterStoreStack(Stack):
    """
    Stack to create SSM Parameters with.

    Parameters are created in a single stack, as many other stacks use the
    Parameters as input. For CloudFormation to work, those entries already
    have to exist before a stack can be created.
    """

    def __init__(self, scope: Construct, id: str, *, maturity: Maturity, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        global g_parameter_store

        Tags.of(self).add("Stack", "Common-ParameterStore")

        self._maturity = maturity.value

        if g_parameter_store is not None:
            raise Exception("Only a single ParameterStoreStack instance can exist")
        g_parameter_store = self

    def get_parameter_name(self, name: str) -> str:
        return f"/{self._maturity}{name}"

    def add_string(self, name: str, default: str) -> ParameterResult:
        if not name.startswith("/"):
            raise Exception("Please use a path for a parameter name")
        parameter_name = self.get_parameter_name(name)

        parameter = StringParameter(
            self,
            parameter_name,
            string_value=default,
            parameter_name=parameter_name,
        )

        return ParameterResult(parameter, parameter_name)

    def add_secure_string(self, name: str) -> ParameterResult:
        if not name.startswith("/"):
            raise Exception("Please use a path for a parameter name")
        parameter_name = self.get_parameter_name(name)

        res = ssm_client.describe_parameters(ParameterFilters=[{"Key": "Name", "Option": "Equals", "Values": [parameter_name]}])
        if not len(res["Parameters"]):
            print(f"ERROR: create SecureString '{parameter_name}' manually (CloudFormation currently can't create those)")

        parameter = StringParameter.from_secure_string_parameter_attributes(
            self,
            parameter_name,
            parameter_name=parameter_name,
            # 'version' is just a dummny value, as in our usage we only care
            # about the ASN (which is identical for every version).
            version=1,
        )

        return ParameterResult(parameter, parameter_name)


def add_string(name: str, default: str) -> ParameterResult:
    if g_parameter_store is None:
        raise Exception("No ParameterStoreStack instance exists")

    return g_parameter_store.add_string(name, default=default)


def add_secure_string(name: str) -> ParameterResult:
    if g_parameter_store is None:
        raise Exception("No ParameterStoreStack instance exists")

    return g_parameter_store.add_secure_string(name)


def get_parameter_name(name: str) -> str:
    if g_parameter_store is None:
        raise Exception("No ParameterStoreStack instance exists")

    return g_parameter_store.get_parameter_name(name)
