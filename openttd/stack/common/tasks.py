from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
)
from aws_cdk.aws_iam import (
    Role,
    ServicePrincipal,
)
from aws_cdk.aws_logs import LogGroup
from typing import Optional

from openttd.stack.common import external

g_tasks = None  # type: Optional[TasksStack]


class TasksStack(Stack):
    """
    Stack to create privileges parts of all tasks.

    To create tasks, we also need an IAM and a LogGroup. This requires extra
    privileges. To avoid having to run redeployments of tasks with these
    extra privileges, it is better to have all those in a single tasks.

    This means that the applications themself can run without any extra
    privileges, allowing them to deploy in an automted fashion.
    """

    def __init__(self,
                 scope: Construct,
                 id: str,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        global g_tasks

        Tag.add(self, "Stack", "Common-Tasks")

        if g_tasks is not None:
            raise Exception("Only a single TasksStack instance can exist")
        g_tasks = self

    def add_logging(self, name: str) -> LogGroup:
        return LogGroup(self, f"LogGroup-{name}")

    def add_role(self, name: str) -> Role:
        role = Role(self, f"Role-{name}",
            assumed_by=ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        external.add_role(role)
        return role


def add_logging(name: str) -> LogGroup:
    if g_tasks is None:
        raise Exception("No TasksStack instance exists")

    return g_tasks.add_logging(name)


def add_role(name: str) -> Role:
    if g_tasks is None:
        raise Exception("No TasksStack instance exists")

    return g_tasks.add_role(name)
