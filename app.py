#!/usr/bin/env python3

import os

from aws_cdk import core
from aws_cdk.core import (
    App,
    Tag,
)

from openttd.enumeration import (
    Deployment,
    Maturity,
)
from openttd.stack.application.binaries_proxy import BinariesProxyStack
from openttd.stack.application.cdn import CdnStack
from openttd.stack.application.docs import DocsStack
from openttd.stack.application.dorpsgek import DorpsgekStack
from openttd.stack.application.redirect import RedirectStack
from openttd.stack.application.website import WebsiteStack
from openttd.stack.common import dns
from openttd.stack.common.alb import AlbStack
from openttd.stack.common.certificate import CertificateStack
from openttd.stack.common.dns import DnsStack
from openttd.stack.common.ecs import EcsStack
from openttd.stack.common.lambda_edge import LambdaEdgeStack
from openttd.stack.common.listener_https import ListenerHttpsStack
from openttd.stack.common.parameter_store import ParameterStoreStack
from openttd.stack.common.policy import PolicyStack
from openttd.stack.common.tasks import TasksStack
from openttd.stack.common.vpc import VpcStack

### Begin of configuration

maturity = Maturity.DEVELOPMENT
env = {
    "region": "eu-central-1",
    "account": os.getenv('AWS_ACCOUNT_ID'),
}
hosted_zone_name = "openttd.org"

### End of configuration

if maturity == Maturity.DEVELOPMENT:
    domain_names = {
        Deployment.PRODUCTION: f"dev.{hosted_zone_name}",
        Deployment.STAGING: f"staging.dev.{hosted_zone_name}",
    }
else:
    domain_names = {
        Deployment.PRODUCTION: f"{hosted_zone_name}",
        Deployment.STAGING: f"staging.{hosted_zone_name}",
    }

app = App()
Tag.add(app, "Maturity", maturity.value)

prefix = f"{maturity.value}-Common-"

LambdaEdgeStack(app, f"{prefix}LambdaEdge",
    env={
        "region": "us-east-1",
        "account": env["account"],
    },
)

DnsStack(app, f"{prefix}Dns",
    hosted_zone_name=hosted_zone_name,
    env=env,
)
TasksStack(app, f"{prefix}Tasks",
    env=env,
)
ParameterStoreStack(app, f"{prefix}ParameterStore",
    maturity=maturity,
    env=env,
)
CertificateStack(app, f"{prefix}Certificate",
    env=env,
)
vpc = VpcStack(app, f"{prefix}Vpc",
    env=env,
)
alb = AlbStack(app, f"{prefix}Alb",
    vpc=vpc.vpc,
    env=env,
)
ecs = EcsStack(app, f"{prefix}Ecs",
    vpc=vpc.vpc,
    env=env,
)

ListenerHttpsStack(app, f"{prefix}Listener-Https",
    alb=alb.alb,
    env=env,
)


for deployment in Deployment:
    prefix = f"{maturity.value}-{deployment.value}-"
    dns.set_domain_name(domain_names[deployment])

    website_policy = PolicyStack(app, f"{prefix}Website-Policy", env=env).policy
    WebsiteStack(app, f"{prefix}Website",
        deployment=deployment,
        policy=website_policy,
        cluster=ecs.cluster,
        env=env,
    )
    binaries_proxy_policy = PolicyStack(app, f"{prefix}BinariesProxy-Policy", env=env).policy
    BinariesProxyStack(app, f"{prefix}BinariesProxy",
        deployment=deployment,
        policy=binaries_proxy_policy,
        cluster=ecs.cluster,
        env=env,
    )

    if deployment == Deployment.PRODUCTION:
        dorpsgek_policy = PolicyStack(app, f"{prefix}Dorpsgek-Policy", env=env).policy
        DorpsgekStack(app, f"{prefix}Dorpsgek",
            deployment=deployment,
            policy=dorpsgek_policy,
            cluster=ecs.cluster,
            env=env,
        )

        CdnStack(app, f"{prefix}Cdn",
            deployment=deployment,
            env=env,
        )

        DocsStack(app, f"{prefix}Docs",
            deployment=deployment,
            env=env,
        )

        RedirectStack(app, f"{prefix}Redirect",
            deployment=deployment,
            env=env,
        )

app.synth()
