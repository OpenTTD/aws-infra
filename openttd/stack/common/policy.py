from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
)

from openttd.construct.policy import Policy


class PolicyStack(Stack):
    """
    Stack to create the policy for an application.

    This splits an application stack into two stacks; one with the application,
    and one that requires additional IAM permissions.
    """

    def __init__(self,
                 scope: Construct,
                 id: str,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Stack", "Common-Policy")
        self._policy = Policy(self, "Policy")

    @property
    def policy(self) -> Policy:
        return self._policy
