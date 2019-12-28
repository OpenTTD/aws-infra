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


class Policy(Construct):
    def __init__(self,
                 scope: Construct,
                 id: str) -> None:
        super().__init__(scope, id)

        policy = ManagedPolicy(self, "Policy")
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
                "cloudformation:DescribeStacks",
            ],
        )

        policy.add_statements(ecs_task)
        policy.add_statements(self._statement)

    def add_role(self, role: IRole) -> None:
        self._statement.add_resources(role.role_arn)

    def add_parameter(self, parameter: IParameter) -> None:
        self._statement.add_resources(parameter.parameter_arn)

    def add_service(self, service: IService) -> None:
        self._statement.add_resources(service.service_arn)

    def add_stack(self, stack: Stack) -> None:
        self._statement.add_resources(stack.stack_id)
