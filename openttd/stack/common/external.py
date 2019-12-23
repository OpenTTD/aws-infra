from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
)
from aws_cdk.aws_ecs import IService
from aws_cdk.aws_iam import (
    ManagedPolicy,
    PolicyStatement,
    IRole,
    User,
)
from aws_cdk.aws_ssm import IParameter
from typing import Optional

g_external = None  # type: Optional[ExternalStack]


class ExternalStack(Stack):
    """
    Stack to create an external user with enough permissions to trigger
    redeployments of containers.

    This is not fully trivial, as it needs enough permissions to for example
    trigger a cloudformation update-stack, which needs access to read the
    ssm parameters, etc etc. This Stack collects all the required permission
    with the lowest amount of access (while being functional, ofc).
    """

    def __init__(self,
                 scope: Construct,
                 id: str,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        global g_external

        Tag.add(self, "Stack", "Common-External")

        user = User(self, "User")

        self._policy = ManagedPolicy(self, "Policy",
            users=[user],
        )
        # (de)registerTaskDefinitions doesn't support specific resources
        ecs_task = PolicyStatement(
            actions=[
                "ecs:DeregisterTaskDefinition",
                "ecs:RegisterTaskDefinition",
            ],
            resources=["*"],
        )
        # All other actions do; as they don't collide, we can spare some bytes
        # and put them in a single statement. (Policies are limit in bytes).
        self._statement = PolicyStatement(
            actions=[
                "iam:PassRole",
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:PutParameter",
                "ecs:UpdateService",
                "ecs:DescribeServices",
                "cloudformation:UpdateStack",
            ],
        )

        self._policy.add_statements(ecs_task)
        self._policy.add_statements(self._statement)

        if g_external is not None:
            raise Exception("Only a single ExternalStack instance can exist")
        g_external = self

    def add_role(self, role: IRole) -> None:
        self._statement.add_resources(role.role_arn)

    def add_parameter(self, parameter: IParameter) -> None:
        self._statement.add_resources(parameter.parameter_arn)

    def add_service(self, service: IService) -> None:
        self._statement.add_resources(service.service_arn)

    def add_stack(self, stack: Stack) -> None:
        self._statement.add_resources(stack.stack_id)


def add_role(role: IRole) -> None:
    if g_external is None:
        raise Exception("No ExternalStack instance exists")

    return g_external.add_role(role)


def add_parameter(parameter: IParameter) -> None:
    if g_external is None:
        raise Exception("No ExternalStack instance exists")

    return g_external.add_parameter(parameter)


def add_service(service: IService) -> None:
    if g_external is None:
        raise Exception("No ExternalStack instance exists")

    return g_external.add_service(service)


def add_stack(stack: Stack) -> None:
    if g_external is None:
        raise Exception("No ExternalStack instance exists")

    return g_external.add_stack(stack)
