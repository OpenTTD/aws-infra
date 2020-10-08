import hashlib

from aws_cdk.core import (
    Construct,
    Fn,
    Stack,
    Tags,
)
from aws_cdk.custom_resources import (
    AwsCustomResource,
    AwsCustomResourcePolicy,
    AwsSdkCall,
    PhysicalResourceId,
)
from aws_cdk.aws_iam import (
    CompositePrincipal,
    ManagedPolicy,
    Role,
    ServicePrincipal,
)
from aws_cdk.aws_lambda import (
    AssetCode,
    Function,
    IVersion,
    Runtime,
    Version,
)
from aws_cdk.aws_ssm import StringParameter
from typing import Optional

from openttd.stack.common import parameter_store

g_lambda_edge = None  # type: Optional[LambdaEdgeStack]


class LambdaEdgeFunction(AwsCustomResource):
    """
    CustomResource to lookup the ARN of a lambda@edge function.
    """

    def __init__(self, scope: Construct, id: str, *, parameter_name: str, **kwargs) -> None:
        kwargs["on_update"] = self._get_on_update_func(id, parameter_name)
        super().__init__(scope, id, **kwargs)

    def _get_on_update_func(self, id: str, parameter_name: str):
        return AwsSdkCall(
            action="getParameter",
            service="SSM",
            parameters={
                "Name": parameter_name,
            },
            region="us-east-1",
            physical_resource_id=PhysicalResourceId.of(f"LEF-{id}"),
        )

    def get_arn(self):
        return self.get_response_field("Parameter.Value")


class LambdaEdgeStack(Stack):
    """
    Lambda@Edge functions have to be stored in us-east-1, while we deploy in
    another region.

    To overcome this cross-region talk, this stack is deployed in us-east-1,
    and creates all the Lambda@Edge functions. After that it updates the
    ParameterStore with the reference, so other stacks can pick this up
    and use it.
    """

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        global g_lambda_edge

        Tags.of(self).add("Stack", "Common-Lambda-Edge")

        self._role = Role(
            self,
            "EdgeLambdaRole",
            assumed_by=CompositePrincipal(
                ServicePrincipal("lambda.amazonaws.com"),
                ServicePrincipal("edgelambda.amazonaws.com"),
            ),
            managed_policies=[
                ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )

        if g_lambda_edge is not None:
            raise Exception("Only a single LambdaEdgeStack instance can exist")
        g_lambda_edge = self

    def create_function(self, other_stack: Stack, id, *, code: AssetCode, handler: str, runtime: Runtime) -> IVersion:
        func = Function(
            self,
            id,
            code=code,
            handler=handler,
            runtime=runtime,
            role=self._role,
        )

        # If code/runtime changes, CDK doesn't re-evaluate the version. In
        # result, we store an old version, and things don't work. But we also
        # don't want to generate a new version every run. The compromise: use
        # the sha256 hash of the index file.
        with open(f"{code.path}/index.js", "rb") as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()
        version = func.add_version(f"Version-{sha256}")

        # Create an entry in the parameter-store that tells the arn of this lambda
        parameter_name = parameter_store.get_parameter_name(f"/LambdaEdge/{id}")
        StringParameter(
            self,
            parameter_name,
            string_value=Fn.join(
                ":",
                [
                    func.function_arn,
                    version.version,
                ],
            ),
            parameter_name=parameter_name,
        )

        other_stack.add_dependency(self)

        # Create a custom resource that fetches the arn of the lambda
        cross_region_func = LambdaEdgeFunction(
            other_stack,
            f"LambdaEdgeFunction-{sha256}",
            parameter_name=parameter_name,
            policy=AwsCustomResourcePolicy.from_sdk_calls(resources=AwsCustomResourcePolicy.ANY_RESOURCE),
        )
        # Create the lambda function based on this arn
        return Version.from_version_arn(other_stack, id, cross_region_func.get_arn())


def create_function(other_stack: Stack, id, *, code: AssetCode, handler: str, runtime: Runtime) -> IVersion:
    if g_lambda_edge is None:
        raise Exception("No LambdaEdgeStack instance exists")

    return g_lambda_edge.create_function(
        other_stack,
        id,
        code=code,
        handler=handler,
        runtime=runtime,
    )
