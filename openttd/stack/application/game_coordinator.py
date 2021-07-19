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
    dns,
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
                "--app",
                "coordinator",
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


class StunServerStack(Stack):
    application_name = "StunServer"
    subdomain_name = "server.stun"
    nlb_subdomain_name = "stun"

    def __init__(self, scope: Construct, id: str, *, deployment: Deployment, policy: Policy, cluster: ICluster, redis_url, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        policy.add_stack(self)

        if deployment == Deployment.PRODUCTION:
            desired_count = 2
            priority = 64
            stun_port = 3975
            database = 1
        else:
            desired_count = 1
            priority = 164
            stun_port = 4975
            database = 2

        sentry_dsn = parameter_store.add_secure_string(f"/StunServer/{deployment.value}/SentryDSN").parameter

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
                "--app",
                "stun",
                "--bind",
                "0.0.0.0",
                "--stun-port",
                str(stun_port),
                "--db",
                "redis",
                "--redis-url",
                "redis://" + redis_url + "/" + str(database),
                "--proxy-protocol",
            ],
            environment={
                "GAME_COORDINATOR_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "GAME_COORDINATOR_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
            },
        )

        self.container.add_port(stun_port)
        nlb.add_nlb(self, self.container.service, Port.tcp(stun_port), self.nlb_subdomain_name, "STUN Server")


class TurnServerStack(Stack):
    application_name = "TurnServer"
    subdomain_name = "server.turn"
    nlb_subdomain_name = "turn"

    def __init__(self, scope: Construct, id: str, *, deployment: Deployment, policy: Policy, cluster: ICluster, redis_url, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        policy.add_stack(self)

        if deployment == Deployment.PRODUCTION:
            desired_count = 2
            priority = 65
            turn_port = 3974
            database = 1
        else:
            desired_count = 1
            priority = 165
            turn_port = 4974
            database = 2

        sentry_dsn = parameter_store.add_secure_string(f"/TurnServer/{deployment.value}/SentryDSN").parameter

        for index in range(1, desired_count + 1):
            container = ECSHTTPSContainer(
                self,
                f"{self.application_name}-{index}",
                subdomain_name=f"{self.subdomain_name}-{index}",
                deployment=deployment,
                policy=policy,
                application_name=f"{self.application_name}-{index}",
                image_name="ghcr.io/openttd/game-coordinator",
                port=80,
                memory_limit_mib=64,
                desired_count=1,
                cluster=cluster,
                priority=priority + index,
                command=[
                    "--app",
                    "turn",
                    "--bind",
                    "0.0.0.0",
                    "--turn-port",
                    str(turn_port - index),
                    "--db",
                    "redis",
                    "--redis-url",
                    "redis://" + redis_url + "/" + str(database),
                    "--proxy-protocol",
                    "--turn-address",
                    dns.subdomain_to_fqdn(f"{self.nlb_subdomain_name}-{index}") + f":{turn_port - index}",
                ],
                environment={
                    "GAME_COORDINATOR_SENTRY_ENVIRONMENT": deployment.value.lower(),
                },
                secrets={
                    "GAME_COORDINATOR_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
                },
            )

            container.add_port(turn_port - index)
            nlb.add_nlb(self, container.service, Port.tcp(turn_port - index), f"{self.nlb_subdomain_name}-{index}", f"TURN Server #{index}")
