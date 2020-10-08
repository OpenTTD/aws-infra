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
from openttd.stack.application.binaries_redirect import BinariesRedirectStack
from openttd.stack.application.cdn import CdnStack
from openttd.stack.application.bananas import (
    BananasApiStack,
    BananasCdnStack,
    BananasFrontendWebStack,
    BananasReload,
    BananasServerStack,
)
from openttd.stack.application.docs import DocsStack
from openttd.stack.application.dorpsgek import DorpsgekStack
from openttd.stack.application.eints import EintsStack
from openttd.stack.application.flyspray import FlysprayStack
from openttd.stack.application.installer import InstallerStack
from openttd.stack.application.master_server import (
    MasterServerStack,
    MasterServerApiStack,
    MasterServerWebStack,
)
from openttd.stack.application.openttd_com import OpenttdComStack
from openttd.stack.application.redirect import RedirectStack
from openttd.stack.application.website import WebsiteStack
from openttd.stack.common import dns
from openttd.stack.common.alb import AlbStack
from openttd.stack.common.certificate import CertificateStack
from openttd.stack.common.dns import DnsStack
from openttd.stack.common.ecs import EcsStack
from openttd.stack.common.lambda_edge import LambdaEdgeStack
from openttd.stack.common.listener_https import ListenerHttpsStack
from openttd.stack.common.nlb_self import NlbStack
from openttd.stack.common.parameter_store import ParameterStoreStack
from openttd.stack.common.policy import PolicyStack
from openttd.stack.common.tasks import TasksStack
from openttd.stack.common.vpc import VpcStack

### Begin of configuration

maturity = Maturity.DEVELOPMENT
env = {
    "region": "eu-central-1",
    "account": os.getenv("AWS_ACCOUNT_ID"),
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

# The NLB has a HTTP site for health-checks. Allow access to it, also from
# the Internet, as that can make debugging a lot easier.
dns.set_domain_name(domain_names[Deployment.PRODUCTION])
nlb = NlbStack(app, f"{prefix}Nlb",
    vpc=vpc.vpc,
    cluster=ecs.cluster,
    ecs_security_group=ecs.security_group,
    ecs_source_security_group=ecs.source_security_group,
    env=env,
)

OpenttdComStack(app, f"{prefix}OpenttdCom",
    deployment=Deployment.PRODUCTION,
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

    # openttd-cdn.org is served via CloudFlare. To allow strict HTTPS
    # connections between CloudFlare and CloudFront, we provision the
    # CloudFront to also accept openttd-cdn.org as domain via HTTPS.
    if deployment == Deployment.PRODUCTION and maturity == Maturity.PRODUCTION:
        additional_fqdns = [
            "bananas.openttd-cdn.org",
        ]
    else:
        additional_fqdns = None

    bananas_cdn = BananasCdnStack(app, f"{prefix}BananasCdn",
        deployment=deployment,
        additional_fqdns=additional_fqdns,
        env=env,
    )
    bananas_api_policy = PolicyStack(app, f"{prefix}BananasApi-Policy", env=env).policy
    bananas_api = BananasApiStack(app, f"{prefix}BananasApi",
        deployment=deployment,
        policy=bananas_api_policy,
        cluster=ecs.cluster,
        bucket=bananas_cdn.bucket,
        env=env,
    )
    BananasReload(app, f"{prefix}BananasApiReload",
        deployment=deployment,
        vpc=vpc.vpc,
        cluster=ecs.cluster,
        service=bananas_api.container.service,
        ecs_security_group=ecs.security_group,
        env=env,
    )

    bananas_server_policy = PolicyStack(app, f"{prefix}BananasServer-Policy", env=env).policy
    bananas_server = BananasServerStack(app, f"{prefix}BananasServer",
        deployment=deployment,
        policy=bananas_server_policy,
        cluster=ecs.cluster,
        bucket=bananas_cdn.bucket,
        env=env,
    )
    BananasReload(app, f"{prefix}BananasServerReload",
        deployment=deployment,
        vpc=vpc.vpc,
        cluster=ecs.cluster,
        service=bananas_server.container.service,
        ecs_security_group=ecs.security_group,
        env=env,
    )

    bananas_frontend_web_policy = PolicyStack(app, f"{prefix}BananasFrontendWeb-Policy", env=env).policy
    BananasFrontendWebStack(app, f"{prefix}BananasFrontendWeb",
        deployment=deployment,
        policy=bananas_frontend_web_policy,
        cluster=ecs.cluster,
        env=env,
    )

    binaries_redirect_policy = PolicyStack(app, f"{prefix}BinariesRedirect-Policy", env=env).policy
    BinariesRedirectStack(app, f"{prefix}BinariesRedirect",
        deployment=deployment,
        policy=binaries_redirect_policy,
        cluster=ecs.cluster,
        env=env,
    )

    FlysprayStack(app, f"{prefix}Flyspray",
        deployment=deployment,
        env=env,
    )

    master_server_policy = PolicyStack(app, f"{prefix}MasterServer-Policy", env=env).policy
    master_server = MasterServerStack(app, f"{prefix}MasterServer",
        deployment=deployment,
        policy=master_server_policy,
        cluster=ecs.cluster,
        env=env,
    )

    master_server_api_policy = PolicyStack(app, f"{prefix}MasterServerApi-Policy", env=env).policy
    master_server_api = MasterServerApiStack(app, f"{prefix}MasterServerApi",
        deployment=deployment,
        policy=master_server_api_policy,
        cluster=ecs.cluster,
        env=env,
    )

    master_server_web_policy = PolicyStack(app, f"{prefix}MasterServerWeb-Policy", env=env).policy
    MasterServerWebStack(app, f"{prefix}MasterServerWeb",
        deployment=deployment,
        policy=master_server_web_policy,
        cluster=ecs.cluster,
        env=env,
    )

    RedirectStack(app, f"{prefix}Redirect",
        deployment=deployment,
        env=env,
    )

    eints_policy = PolicyStack(app, f"{prefix}Eints-Policy", env=env).policy
    EintsStack(app, f"{prefix}Eints",
        deployment=deployment,
        policy=eints_policy,
        cluster=ecs.cluster,
        vpc=vpc.vpc,
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

        # openttd-cdn.org is served via CloudFlare. To allow strict HTTPS
        # connections between CloudFlare and CloudFront, we provision the
        # CloudFront to also accept openttd-cdn.org as domain via HTTPS.
        if maturity == Maturity.PRODUCTION:
            additional_fqdns = [
                "www.openttd-cdn.org",
                "openttd-cdn.org",
            ]
        else:
            additional_fqdns = None
        CdnStack(app, f"{prefix}Cdn",
            deployment=deployment,
            additional_fqdns=additional_fqdns,
            env=env,
        )

        # openttd-cdn.org is served via CloudFlare. To allow strict HTTPS
        # connections between CloudFlare and CloudFront, we provision the
        # CloudFront to also accept openttd-cdn.org as domain via HTTPS.
        if maturity == Maturity.PRODUCTION:
            additional_fqdns = [
                "installer.openttd-cdn.org",
            ]
        else:
            additional_fqdns = None
        InstallerStack(app, f"{prefix}Installer",
            deployment=deployment,
            additional_fqdns=additional_fqdns,
            env=env,
        )

        DocsStack(app, f"{prefix}Docs",
            deployment=deployment,
            env=env,
        )

app.synth()
