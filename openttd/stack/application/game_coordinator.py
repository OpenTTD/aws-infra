from aws_cdk.core import (
    Construct,
    Stack,
    Tags,
)
from aws_cdk.aws_ecs import (
    ICluster,
    Secret,
)
from aws_cdk.aws_ec2 import Port

from openttd.construct.ecs_https_container import ECSHTTPSContainer
from openttd.construct.policy import Policy
from openttd.enumeration import Deployment
from openttd.stack.common import (
    nlb_self as nlb,
    parameter_store,
)


class GameCoordinatorStack(Stack):
    application_name = "GameCoordinator"
    subdomain_name = "server.coordinator"
    nlb_subdomain_name = "coordinator"

    def __init__(self, scope: Construct, id: str, *, deployment: Deployment, policy: Policy, cluster: ICluster, redis_url, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        policy.add_stack(self)

        if deployment == Deployment.PRODUCTION:
            desired_count = 2
            priority = 63
            coordinator_port = 3976
            database = 1
        else:
            desired_count = 1
            priority = 163
            coordinator_port = 4976
            database = 2

        sentry_dsn = parameter_store.add_secure_string(f"/GameCoordinator/{deployment.value}/SentryDSN").parameter
        shared_secret = parameter_store.add_secure_string(f"/GameCoordinator/{deployment.value}/SharedSecret").parameter

        self.container = ECSHTTPSContainer(
            self,
            self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="ghcr.io/openttd/game-coordinator",
            port=80,
            memory_limit_mib=64,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--bind",
                "0.0.0.0",
                "--coordinator-port",
                str(coordinator_port),
                "--db",
                "redis",
                "--redis-url",
                "redis://" + redis_url + "/" + str(database),
                "--proxy-protocol",
                "--socks-proxy",
                "socks5://nlb.openttd.internal:8080",
            ],
            environment={
                "GAME_COORDINATOR_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "GAME_COORDINATOR_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
                "GAME_COORDINATOR_SHARED_SECRET": Secret.from_ssm_parameter(shared_secret),
            },
        )

        self.container.add_port(coordinator_port)
        nlb.add_nlb(self, self.container.service, Port.tcp(coordinator_port), self.nlb_subdomain_name, "Game Coordinator")
