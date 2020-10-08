from aws_cdk.core import (
    Construct,
    Stack,
)
from aws_cdk.aws_ecs import (
    ICluster,
    IService,
)
from aws_cdk.aws_iam import (
    ManagedPolicy,
    PolicyStatement,
    IRole,
)
from aws_cdk.aws_ssm import IParameter


class Policy(Construct):
    def __init__(self, scope: Construct, id: str) -> None:
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
        # ListTagsForResource cannot be set for a service only, but has to be
        # on the cluster (despite it only looking at the tags for the service).
        # We make a separate statement for this, to avoid giving other polcies
        # more rights than required, as they can be per service.
        self._cluster_statement = PolicyStatement(
            actions=[
                "ecs:ListTagsForResource",
            ],
        )
        # All other actions can be combined, as they don't collide. As policies
        # have a maximum amount of bytes they can consume, this spares a few of
        # them.
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
        policy.add_statements(self._cluster_statement)
        policy.add_statements(self._statement)

    def add_role(self, role: IRole) -> None:
        self._statement.add_resources(role.role_arn)

    def add_parameter(self, parameter: IParameter) -> None:
        self._statement.add_resources(parameter.parameter_arn)

    def add_service(self, service: IService) -> None:
        self._statement.add_resources(service.service_arn)

    def add_cluster(self, cluster: ICluster) -> None:
        self._cluster_statement.add_resources(cluster.cluster_arn)

    def add_stack(self, stack: Stack) -> None:
        self._statement.add_resources(stack.stack_id)
